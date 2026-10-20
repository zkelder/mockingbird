#!/usr/bin/env python3
"""Prepare a disposable, conspicuously-labelled MockingBird DEMO instance.

Why this exists: a visitor should be able to experience the whole loop
(Observe -> Discover -> Understand -> Confirm -> Remember -> Improve) without a
bird appearing in front of a live camera. This script feeds two real,
public-domain (CC0) recorded wildlife clips through the *unmodified*
production path -- recorded-video import, the real MegaDetector v5a
Observation Engine, tracking, Visit admission, and the real BioCLIP 2
identification assistant. Nothing is simulated: the Visits are the detector's
genuine output on that footage, and every species result is a *suggestion*
until a human confirms or corrects it in the Review Queue.

Isolation (the doctrine's "never mistaken for real evidence" rule):
  * Run it only against a throwaway instance started with its own
    ``MOCKINGBIRD_HOME`` (see docs/portfolio-demo-walkthrough.md). It refuses
    to touch an instance that already holds a non-DEMO camera.
  * Everything it creates is named ``DEMO ...`` and the instance is renamed
    "MockingBird DEMO ...", so it is visible on the sign-in screen and in the
    Cameras list.
  * It never writes a review decision. Confirmation is left to the viewer.

What it needs: a running instance (``python -m mockingbird``), ffmpeg on PATH
(only for ``--fetch-media`` transcoding), and network access *only* when
``--fetch-media`` is passed (an explicit, one-time download of two CC0 files
from Wikimedia Commons, SHA-1 verified against the manifest). Media is stored
under ``data/demo-media/`` (git-ignored) and is never committed.

Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / "demo" / "demo-media-manifest.json"
DEFAULT_MEDIA_DIR = REPO_ROOT / "data" / "demo-media"
DEMO_PREFIX = "DEMO"
DEMO_CAMERA_NAME = "DEMO sample clips (recorded, not a live camera)"
DEMO_STREAM_NAME = "DEMO recorded clips"
DEMO_INSTALLATION_NAME = "MockingBird DEMO - public-domain sample clips"
USER_AGENT = "MockingBirdDemoPrep/1.0 (portfolio demo; one-time CC0 fetch)"


class DemoPrepError(RuntimeError):
    pass


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["clips"]


def fetch_media(media_dir: Path) -> None:
    """Explicit one-time download + transcode of the CC0 manifest clips."""
    if shutil.which("ffmpeg") is None:
        raise DemoPrepError("ffmpeg is required on PATH to prepare the demo clips (--fetch-media).")
    media_dir.mkdir(parents=True, exist_ok=True)
    for clip in load_manifest():
        target = media_dir / clip["demo_filename"]
        if target.exists():
            print(f"  have {target.name}")
            continue
        source = media_dir / clip["source_filename"]
        if not source.exists():
            print(f"  downloading {clip['source_filename']} ({clip['license']}) ...")
            request = urllib.request.Request(clip["download_url"], headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response:
                source.write_bytes(response.read())
        digest = hashlib.sha1(source.read_bytes()).hexdigest()  # noqa: S324 - Commons publishes SHA-1
        if digest != clip["sha1"]:
            source.unlink()
            raise DemoPrepError(f"SHA-1 mismatch for {clip['source_filename']}: refusing to use it.")
        # MockingBird imports mp4/mov; transcode only (video track, no audio).
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-i", str(source), "-an",
                "-c:v", "libx264", "-crf", "24", "-preset", "fast", "-pix_fmt", "yuv420p",
                str(target),
            ],
            check=True,
        )
        print(f"  prepared {target.name}")


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def call(self, method: str, path: str, payload=None, *, raw=None, headers=None):
        data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        merged = {"Content-Type": "application/json"} if raw is None else {}
        merged.update(headers or {})
        request = urllib.request.Request(self.base + path, method=method, data=data, headers=merged)
        try:
            with self.opener.open(request, timeout=1800) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            raise DemoPrepError(f"{method} {path} -> HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise DemoPrepError(f"Could not reach {self.base}: {error.reason}") from error
        return json.loads(body) if body else None


def multipart(fields: dict[str, str], filename: str, content: bytes, content_type: str):
    boundary = uuid.uuid4().hex
    body = b""
    for key, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def sign_in_or_bootstrap(client: Client, username: str, password: str) -> None:
    try:
        client.call("POST", "/api/setup/administrator", {
            "display_name": "Demo Admin", "login_identity": username, "password": password,
        })
        print("  created the demo administrator account")
        return
    except DemoPrepError as error:
        if "409" not in str(error):
            raise
    client.call("POST", "/api/auth/sign-in", {"login_identity": username, "password": password})
    print("  signed in to the existing demo administrator account")


def assert_instance_is_disposable(client: Client) -> dict | None:
    """Refuse a non-demo instance; return the existing DEMO camera, if any."""
    existing_demo = None
    for source in client.call("GET", "/api/sources"):
        if source.get("kind") == "demo":
            continue  # the product's own seeded, already-isolated sample Source
        if source["name"].startswith(DEMO_PREFIX):
            existing_demo = source
            continue
        raise DemoPrepError(
            f"This instance already has a non-demo camera ({source['name']!r}). Run the demo on a "
            "fresh MOCKINGBIRD_HOME instead -- see docs/portfolio-demo-walkthrough.md."
        )
    return existing_demo


def prepare(client: Client, media_dir: Path, username: str, password: str, identify: bool) -> None:
    sign_in_or_bootstrap(client, username, password)
    existing = assert_instance_is_disposable(client)

    clips = load_manifest()
    for clip in clips:
        if not (media_dir / clip["demo_filename"]).exists():
            raise DemoPrepError(f"{clip['demo_filename']} missing in {media_dir}; re-run with --fetch-media.")

    client.call("PUT", "/api/admin/installation-settings", {"installation_name": DEMO_INSTALLATION_NAME})
    # The demo camera below replaces the wizard's camera step, so land the
    # viewer in the product. (To see first-run onboarding itself, open a fresh
    # MOCKINGBIRD_HOME in the browser *before* running this script.)
    client.call("PUT", "/api/setup/state", {"current_step": "done", "completed": True})

    if existing is not None:
        streams = client.call("GET", f"/api/sources/{existing['id']}/streams")
        stream_id = streams[0]["id"]
        print("  reusing the existing DEMO camera; skipping already-imported clips")
    else:
        completed = client.call("POST", "/api/camera-setup/complete", {
            "camera_name": DEMO_CAMERA_NAME,
            "stream_name": DEMO_STREAM_NAME,
            "provider_key": "manual_media",
            "config": {"source_label": "DEMO CC0 sample clips"},
            "zones": [{
                "name": "Whole view", "zone_type": "yard",
                "polygon": [{"x": 0.02, "y": 0.02}, {"x": 0.98, "y": 0.02}, {"x": 0.98, "y": 0.98}, {"x": 0.02, "y": 0.98}],
            }],
            "enable_monitoring": False,
            "idempotency_key": "demo-camera-" + uuid.uuid4().hex[:12],
        })
        stream_id = completed["stream"]["id"]
        print(f"  created {DEMO_CAMERA_NAME!r}")

    already = {asset["original_filename"] for asset in client.call("GET", "/api/media")}
    visit_ids: list[str] = []
    for clip in clips:
        name = clip["demo_filename"]
        if name in already:
            continue
        body, headers = multipart(
            {
                "stream_id": stream_id,
                "title": f"DEMO CC0 clip - {clip['subject']}",
                "notes": f"DEMO: public-domain (CC0) sample clip by {clip['author']} via Wikimedia Commons. "
                         "Not from a live camera; not this Place's own wildlife.",
            },
            name, (media_dir / name).read_bytes(), "video/mp4",
        )
        imported = client.call("POST", "/api/media/import", raw=body, headers=headers)
        media_id = imported["media_asset"]["id"]
        print(f"  imported {name} as {media_id}; running the real Observation Engine ...")
        result = client.call("POST", f"/api/media/{media_id}/analyze-recorded", {})
        if result["status"] != "completed":
            raise DemoPrepError(
                f"Analysis of {name} did not complete: {result.get('error_code')} - {result.get('error_message')}"
            )
        print(f"    {result['frames_analyzed']} frames analyzed -> {result['visits_created']} candidate Visit(s)")
        visit_ids += result["visit_ids"]

    if identify:
        for visit_id in visit_ids:
            outcome = client.call("POST", f"/api/review-queue/visit/{visit_id}/identify", {})
            print(f"  identification assistant for {visit_id}: {outcome.get('status', 'requested')} (suggestion only)")

    print("\nDemo instance is ready. Nothing has been confirmed: open Review and judge the Visits yourself.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--media-dir", type=Path, default=DEFAULT_MEDIA_DIR)
    parser.add_argument("--fetch-media", action="store_true",
                        help="Explicitly download + transcode the two CC0 clips (needs network and ffmpeg).")
    parser.add_argument("--username", default="demo")
    parser.add_argument("--password", default="Mockingbird-Demo-2026!",
                        help="Disposable demo-only credential for the throwaway instance.")
    parser.add_argument("--no-identify", action="store_true",
                        help="Skip the explicit identification-assistant request (suggestions).")
    args = parser.parse_args(argv)
    try:
        if args.fetch_media:
            print("Preparing demo clips:")
            fetch_media(args.media_dir)
        print(f"Preparing demo instance at {args.api_base}:")
        prepare(Client(args.api_base), args.media_dir, args.username, args.password, not args.no_identify)
    except DemoPrepError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
