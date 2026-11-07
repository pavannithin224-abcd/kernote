"""Settings. Local-first by default: no network, no telemetry, localhost only."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KERNOTE_", env_file=".env")

    # platformdirs keeps this correct on Windows and Linux without guessing at
    # %APPDATA% (risk R4 in docs/ARCHITECTURE.md).
    data_dir: Path = Path(user_data_dir("kernote", "kernote"))
    host: str = "127.0.0.1"
    port: int = 8787
    # The Vite dev origin is the only allowed browser origin.
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    # Scanner limits. Read-only always; these bound what is even read.
    max_file_bytes: int = 1_000_000
    max_files_per_scan: int = 20_000

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kernote.db"


settings = Settings()
