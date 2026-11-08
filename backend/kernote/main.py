"""FastAPI application factory.

Binds 127.0.0.1 only and allows exactly the Vite dev origin. No telemetry, no
outbound calls (ARCHITECTURE.md §7).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from .api import deps
from .api.routers import maintenance, memories, projects
from .config import settings
from .db.connection import open_db

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
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
        return {
            "status": "ok",
            "schema_version": row["value"],
            "db_path": str(settings.db_path),
        }

    return app


app = create_app()
