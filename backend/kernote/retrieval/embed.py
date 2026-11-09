"""Local embeddings via fastembed (ADR-0011, ADR-0023).

Two constraints shape this module.

**No torch.** `fastembed` runs the ONNX export on `onnxruntime`; a dry-run of
the install confirms numpy, onnxruntime and tokenizers and no torch, so
ADR-0004's rule survives.

**No network by default.** `CLAUDE.md` forbids outbound calls unless the user
opts in, and the model weights are a ~90 MB download on first use. So:

* `status()` reports whether the model is already on disk, using the filesystem
  only — it never touches the network.
* `ensure_model()` is the only function that may download, and it refuses
  unless explicitly allowed.
* Retrieval degrades to keyword-only when the model is absent. That is not a
  broken state: FTS5-alone is also the baseline ADR-0014 measures against.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import structlog

from ..config import settings

log = structlog.get_logger(__name__)

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384
APPROX_DOWNLOAD_MB = 90

_lock = threading.Lock()
_model = None


def cache_dir() -> Path:
    """Where the weights live.

    Deliberately *not* under `settings.data_dir`: the model is a shared,
    re-downloadable asset rather than project data, and putting it there meant
    every new data directory triggered another 90 MB fetch.
    """
    return settings.model_cache_dir


@dataclass(frozen=True)
class EmbedStatus:
    model_id: str
    dim: int
    cached: bool
    enabled: bool
    cache_path: str
    download_mb: int

    @property
    def usable(self) -> bool:
        return self.cached and self.enabled


def status() -> EmbedStatus:
    """Filesystem-only check. Never performs a network request."""
    directory = cache_dir()
    slug = MODEL_ID.replace("/", "_")
    cached = False
    if directory.is_dir():
        # fastembed lays out `models--org--name/`; match loosely so a layout
        # change degrades to "not cached" rather than a crash.
        cached = (
            any(
                "all-minilm-l6" in child.name.lower().replace("_", "-")
                for child in directory.rglob("*")
                if child.is_dir()
            )
            or (directory / slug).is_dir()
        )
    return EmbedStatus(
        model_id=MODEL_ID,
        dim=DIM,
        cached=cached,
        enabled=settings.embeddings_enabled,
        cache_path=str(directory),
        download_mb=APPROX_DOWNLOAD_MB,
    )


def ensure_model(*, allow_download: bool = False):
    """The loaded model, or None.

    `allow_download=True` is the user's explicit opt-in; without it this will
    not reach the network even if the model is missing.
    """
    global _model
    with _lock:
        if _model is not None:
            return _model
        current = status()
        if not current.cached and not allow_download:
            log.info(
                "embed.unavailable",
                reason="model not cached and download not permitted",
                model=MODEL_ID,
            )
            return None
        try:
            from fastembed import TextEmbedding
        except ImportError:
            log.warning("embed.fastembed_missing")
            return None
        cache_dir().mkdir(parents=True, exist_ok=True)
        if not current.cached:
            log.warning(
                "embed.downloading",
                model=MODEL_ID,
                approx_mb=APPROX_DOWNLOAD_MB,
                destination=str(cache_dir()),
                note="explicit user opt-in; model weights only, no telemetry",
            )
        try:
            _model = TextEmbedding(model_name=MODEL_ID, cache_dir=str(cache_dir()))
        except Exception as exc:  # noqa: BLE001 - never fail a scan on this
            log.warning("embed.load_failed", model=MODEL_ID, error=str(exc))
            return None
        log.info("embed.ready", model=MODEL_ID, dim=DIM)
        return _model


def encode(texts: list[str], *, allow_download: bool = False) -> list[list[float]]:
    """L2-normalised vectors, or [] when the model is unavailable.

    Returning empty rather than raising is deliberate: a caller that cannot
    embed should fall back to keyword search, not fail the request.
    """
    if not texts:
        return []
    model = ensure_model(allow_download=allow_download)
    if model is None:
        return []
    import numpy as np

    vectors = np.asarray(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    # A zero vector would divide by zero and poison every later cosine.
    norms[norms == 0] = 1.0
    return (vectors / norms).tolist()


def reset_for_tests() -> None:
    global _model
    with _lock:
        _model = None
