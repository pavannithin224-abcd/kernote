"""FastAPI application factory.

Binds 127.0.0.1 only and allows exactly the Vite dev origin. No telemetry, no
outbound calls (ARCHITECTURE.md §7).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import FileResponse, JSONResponse

from .api import deps
from .api.routers import (
    admin,
    agents,
    ask,
    evaluation,
    maintenance,
    memories,
    projects,
)
from .config import settings
from .db.connection import open_db
from .logging import configure_logging

# stderr, not stdout: see kernote/logging.py. Shared with the MCP server so
# the two entry points cannot disagree about where diagnostics go.
configure_logging()
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = open_db(settings.db_path)
    deps.set_db(conn)
    version = conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()["value"]
    log.info("kernote.start", db=str(settings.db_path), schema_version=version)
    try:
        yield
    finally:
        conn.close()
        log.info("kernote.stop")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kernote",
        description="Reviewable project memory. Local-first.",
        version="0.1.0",
        lifespan=lifespan,
    )
    # Only when a cross-origin caller is actually expected. In development
    # the UI is on :5173 and the API here, so the default list allows that
    # one origin. Served as a single process there is only one origin and
    # the middleware is pure attack surface, so `just app`, `scripts/app.sh`
    # and the desktop launcher set `KERNOTE_CORS_ORIGINS=[]` and it is never
    # registered.
    #
    # Keyed on configuration rather than on "is there a build?", because a
    # `dist/` left on disk from an earlier build is exactly the state
    # `just dev` runs in -- guessing from it would break the dev loop.
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["*"],
        )
    app.include_router(projects.router)
    app.include_router(memories.router)
    app.include_router(maintenance.router)
    app.include_router(ask.router)
    app.include_router(agents.router)
    app.include_router(evaluation.router)
    app.include_router(admin.router)

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        # Domain invariants raise ValueError. Surface them, do not swallow them.
        log.warning("domain.rejected", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict:
        conn = deps.db()
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        # Size on disk includes the -wal and -shm sidecars. In WAL mode the
        # write-ahead log routinely holds megabytes that have not been
        # checkpointed into the main file yet, so reporting only the .db
        # understates what Kernote actually occupies.
        db_bytes = 0
        for suffix in ("", "-wal", "-shm"):
            sidecar = settings.db_path.with_name(settings.db_path.name + suffix)
            if sidecar.is_file():
                db_bytes += sidecar.stat().st_size
        return {
            "status": "ok",
            "schema_version": row["value"],
            "db_path": str(settings.db_path),
            "db_bytes": db_bytes,
        }

    _serve_frontend(app)
    return app


def web_dist() -> Path | None:
    """Where the built UI lives, or None if it has not been built.

    Explicit setting first, so a packaged app can point anywhere; otherwise
    the repository's own `frontend/dist`.
    """
    if settings.web_dist is not None:
        configured = Path(settings.web_dist)
        return configured if (configured / "index.html").is_file() else None
    default = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return default if (default / "index.html").is_file() else None


def _cache_headers(asset_path: str) -> dict[str, str]:
    """Immutable for content-hashed files, revalidate for everything else.

    Vite emits `assets/index-<hash>.js`: the name changes whenever the bytes
    do, so the file can be cached for a year and never revalidated. Anything
    else keeps its name across builds, so it must be checked each time.

    Without this the browser revalidated every file on every load -- a 500 KB
    bundle re-fetched or 304-ed on each visit to a local-first app that is
    supposed to start instantly.
    """
    if asset_path.startswith("assets/"):
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    return {"Cache-Control": "no-cache"}


def _serve_frontend(app: FastAPI) -> None:
    """Serve the built UI from this process, so Kernote is one command.

    Registered *after* the routers, so every API path is matched first and
    nothing here can shadow one. Two rules matter:

    * **An unknown API path stays JSON.** Falling through to `index.html`
      would hand a caller 200 and a page of HTML where it expected a 404 and
      a body it can parse -- which is how a typo in a client becomes a silent
      mystery instead of an error.
    * **Anything else falls back to `index.html`**, because the UI is a
      single-page app: `/graph` is a client-side route, not a file, and a
      hard reload there must not 404.

    Without a build this does nothing at all and the API runs alone, which is
    the development arrangement -- Vite serves the UI on its own port.
    """
    dist = web_dist()
    if dist is None:
        log.info("web.not_built", hint="run `npm --prefix frontend run build`")
        return

    index = dist / "index.html"

    @app.get("/{asset_path:path}", include_in_schema=False)
    def spa(asset_path: str) -> FileResponse:
        if asset_path == "health" or asset_path.startswith(("api/", "docs", "openapi")):
            raise HTTPException(404, "not found")

        if asset_path:
            candidate = (dist / asset_path).resolve()
            # `resolve()` collapses any `..`; the containment check is what
            # stops a crafted path reaching outside the build directory.
            if candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate, headers=_cache_headers(asset_path))

        # The shell is never cached. It names the hashed assets, so a stale
        # copy would point at files that no longer exist -- a blank app after
        # an upgrade, fixed only by a hard refresh the user has no reason to
        # guess at.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    log.info("web.serving", path=str(dist))


app = create_app()
