"""Same-origin hosting for the built MockingBird web application."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from fastapi import HTTPException
from starlette.responses import FileResponse, HTMLResponse, Response


WEB_DIST_ENV_VAR = "MOCKINGBIRD_WEB_DIST"
_RESERVED_ROOT_PATHS = {
    "api",
    "docs",
    "health",
    "openapi.json",
    "redoc",
}


@dataclass(frozen=True)
class FrontendBuildStatus:
    dist_path: Path
    index_path: Path
    available: bool


def find_workspace_root(start: Path | None = None) -> Path | None:
    """Find a development checkout without making runtime data depend on the caller CWD."""

    candidate = (start or Path(__file__)).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "web").is_dir():
            return parent
    return None


def resolve_frontend_dist(explicit_path: str | Path | None = None) -> Path:
    """Resolve a packaged build first, then a development-checkout build."""

    configured_path = explicit_path or os.getenv(WEB_DIST_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    packaged_dist = Path(__file__).resolve().parent / "web_dist"
    if (packaged_dist / "index.html").is_file():
        return packaged_dist

    workspace_root = find_workspace_root()
    if workspace_root is not None:
        return workspace_root / "web" / "dist"
    return packaged_dist


def frontend_build_status(explicit_path: str | Path | None = None) -> FrontendBuildStatus:
    dist_path = resolve_frontend_dist(explicit_path)
    index_path = dist_path / "index.html"
    return FrontendBuildStatus(
        dist_path=dist_path,
        index_path=index_path,
        available=index_path.is_file(),
    )


def frontend_response(full_path: str) -> Response:
    """Serve a built asset or the SPA entry document without masking API 404s."""

    normalized_path = full_path.strip("/")
    root_segment = normalized_path.split("/", 1)[0] if normalized_path else ""
    if root_segment in _RESERVED_ROOT_PATHS:
        raise HTTPException(status_code=404, detail="Not Found")

    status = frontend_build_status()
    if not status.available:
        return HTMLResponse(
            status_code=503,
            headers={"Cache-Control": "no-store"},
            content=(
                "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>MockingBird is preparing</title></head><body>"
                "<main><h1>MockingBird interface is not ready yet.</h1>"
                "<p>Build the local web interface, then restart MockingBird.</p>"
                "</main></body></html>"
            ),
        )

    if normalized_path:
        candidate = (status.dist_path / normalized_path).resolve()
        try:
            candidate.relative_to(status.dist_path.resolve())
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Not Found") from error

        if candidate.is_file():
            return FileResponse(
                candidate,
                headers={
                    "Cache-Control": (
                        "public, max-age=31536000, immutable"
                        if root_segment == "assets"
                        else "no-cache"
                    )
                },
            )
        if Path(normalized_path).suffix:
            raise HTTPException(status_code=404, detail="Not Found")

    return FileResponse(
        status.index_path,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )
