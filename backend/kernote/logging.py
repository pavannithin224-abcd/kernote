"""Logging configuration, shared by every entry point.

**Logs go to stderr, never stdout.** For the stdio MCP server, stdout *is* the
JSON-RPC transport: a single log line written there corrupts the protocol and
the client hangs with no error. Found by driving the real server over stdio
rather than unit-testing the tool functions, which would never have shown it.
stderr is also the conventional place for a service's diagnostics, so this is
the right default for the HTTP API too, not an MCP-specific workaround.

The stream is resolved **at write time**, not at configure time. Binding
`sys.stderr` once meant anything that replaced it afterwards left the logger
holding a closed file: pytest's `capsys` did exactly that, and a single test
then poisoned every later log call in the suite with
`ValueError: I/O operation on closed file`.
"""

from __future__ import annotations

import contextlib
import sys
from typing import TextIO

import structlog

_configured = False


_log_file: TextIO | None = None


def _fallback_log_file() -> TextIO:
    """Open `<data_dir>/logs/kernote.log` once, for processes with no stderr."""
    global _log_file
    if _log_file is None or _log_file.closed:
        from .config import settings

        log_dir = settings.data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _log_file = open(  # noqa: SIM115 - process-lifetime handle by design
            log_dir / "kernote.log", "a", encoding="utf-8", buffering=1
        )
    return _log_file


class _LateBoundStream:
    """Writes to whatever `sys.stderr` is *now*.

    A supervisor, a reload, or a test harness can all swap the process streams;
    a logger that captured the old object would either write nowhere or raise.
    """

    def __init__(self, override: TextIO | None = None) -> None:
        self._override = override

    @property
    def _target(self) -> TextIO:
        if self._override is not None:
            return self._override
        if sys.stderr is not None:
            return sys.stderr
        # A windowed (no-console) build has no stderr at all: `sys.stderr` is
        # None, and writing to it used to kill the process on the first log
        # line with nothing to read. Fall back to a log file in the data dir.
        return _fallback_log_file()

    def write(self, text: str) -> int:
        target = self._target
        try:
            written = target.write(text)
        except (ValueError, AttributeError):
            # The stream went away mid-flight. Diagnostics must never be the
            # reason a request fails.
            return 0
        return written if isinstance(written, int) else 0

    def flush(self) -> None:
        with contextlib.suppress(ValueError, AttributeError):
            self._target.flush()

    def isatty(self) -> bool:
        try:
            return bool(self._target.isatty())
        except (ValueError, AttributeError):
            return False


def configure_logging(stream: TextIO | None = None, *, force: bool = False) -> None:
    global _configured
    if _configured and not force:
        return
    sink = _LateBoundStream(stream)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            # Colour only for a real terminal; decided per write, since the
            # stream can change.
            structlog.dev.ConsoleRenderer(colors=sink.isatty()),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sink),
    )
    _configured = True
