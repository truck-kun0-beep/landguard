"""Local demo server.

Boots the FastAPI app from `backend.main` and mounts the `frontend/`
directory at `/frontend` so both the API (`/api/*`) and the static UI
are served from one process.

Run with:
    python -m uvicorn serve_frontend:app --reload --port 8000

Set LANDGUARD_NOCACHE=1 (or any truthy value) to disable HTTP caching
for frontend assets. Useful while iterating on HTML/CSS/JS &mdash; you
no longer need a hard reload after every edit.
"""
from __future__ import annotations

import os

from starlette.staticfiles import StaticFiles

from backend.main import app

_FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend"))


def _has_mount(prefix: str) -> bool:
    for route in app.router.routes:
        if getattr(route, "path", "").rstrip("/") == prefix.rstrip("/"):
            return True
    return False


_NOCACHE = bool(os.environ.get("LANDGUARD_NOCACHE"))


class _NoCacheStaticFiles(StaticFiles):
    """StaticFiles variant sending aggressive no-cache headers.

    Browsers otherwise reuse the on-disk copy of CSS/JS/HTML across
    edits, which is annoying during a demo. The headers below force a
    revalidation on every request.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp


if not _has_mount("/frontend"):
    cls = _NoCacheStaticFiles if _NOCACHE else StaticFiles
    app.mount("/frontend", cls(directory=_FRONTEND_DIR, html=True), name="frontend")