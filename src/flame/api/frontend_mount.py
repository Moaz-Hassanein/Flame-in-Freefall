"""Serve the built React app from FastAPI (Phase 10).

Call mount_frontend(app) as the LAST registration in create_app(), after all
/api routers.

- If frontend/dist/index.html does not exist (e.g. in dev), nothing is mounted.
- /assets/* and other real files are served from dist.
- Any other path falls back to index.html (SPA), EXCEPT /api and /api/*,
  which return a JSON 404 so the frontend never shadows API routes.
- The catch-all is excluded from the OpenAPI schema, so docs/openapi.json is unchanged.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# src/flame/api/frontend_mount.py -> repo root is parents[3]
DEFAULT_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def mount_frontend(app: FastAPI, dist: Path = DEFAULT_DIST) -> None:
    dist = Path(dist).resolve()
    index = dist / "index.html"
    if not index.is_file():
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
