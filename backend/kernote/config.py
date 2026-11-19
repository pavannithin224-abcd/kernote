"""Settings. Local-first by default: no network, no telemetry, localhost only."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KERNOTE_", env_file=".env")

    # platformdirs keeps this correct on Windows and Linux without guessing at
    # %APPDATA% (risk R4 in docs/ARCHITECTURE.md).
    data_dir: Path = Path(user_data_dir("kernote", "kernote"))
    host: str = "127.0.0.1"
    port: int = 8787
    # Host headers the API answers to. Anything else is refused: see security.py.
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
    # The Vite dev origin is the only allowed browser origin.
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    # The built frontend, served by this same process so Kernote runs as one
    # command on one port (Q4). `None` means "look beside the repository";
    # a packaged build sets KERNOTE_WEB_DIST to wherever it put the assets.
    # When the directory does not exist the app simply serves no UI, which is
    # the normal state during development -- Vite serves it on :5173 instead.
    web_dist: Path | None = None

    # Scanner limits. Read-only always; these bound what is even read.
    max_file_bytes: int = 1_000_000
    max_files_per_scan: int = 20_000

    # Semantic retrieval is opt-in because the model weights are a ~90 MB
    # download and `CLAUDE.md` forbids outbound calls by default. With this
    # off, retrieval is keyword-only -- which is also ADR-0014's baseline, not
    # a degraded state (ADR-0023).
    embeddings_enabled: bool = False
    # The model weights are a shared, re-downloadable asset, not project data,
    # so they live in the user cache rather than under `data_dir`. Keeping them
    # in `data_dir` meant relocating the database re-downloaded 90 MB.
    model_cache_dir: Path = Path(user_cache_dir("kernote", "kernote")) / "models"
    # Permits the one-time model fetch. Separate from `embeddings_enabled` so
    # enabling search on an already-cached model never implies a download.
    embeddings_allow_download: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kernote.db"


settings = Settings()
