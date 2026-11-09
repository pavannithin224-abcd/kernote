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


class _LateBoundStream:
    """Writes to whatever `sys.stderr` is *now*.

    A supervisor, a reload, or a test harness can all swap the process streams;
    a logger that captured the old object would either write nowhere or raise.
    """

    def __init__(self, override: TextIO | None = None) -> None:
        self._override = override

    @property
    def _target(self) -> TextIO:
        return self._override if self._override is not None else sys.stderr

    def write(self, text: str) -> int:
        target = self._target
        try:
            written = target.write(text)
        except ValueError:
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
