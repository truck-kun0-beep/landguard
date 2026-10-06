"""Local demo server.

Boots the FastAPI app from `backend.main` and mounts the `frontend/`
directory at `/frontend` so both the API (`/api/*`) and the static UI
are served from one process.

Run with:
    python -m uvicorn serve_frontend:app --reload --port 8000
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


if not _has_mount("/frontend"):
    app.mount("/frontend", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")