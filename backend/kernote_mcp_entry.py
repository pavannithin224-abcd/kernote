"""Entry point for the packaged `kernote-mcp.exe`.

Kept apart from `kernote/__main__.py` for a reason that is specific to
Windows: the app itself is built as a *windowed* program (no console), and a
windowed process has no stdin/stdout, so it cannot be an MCP stdio server --
the JSON-RPC transport *is* stdin/stdout. This one is built as a console
program, shares every library with the app (see kernote.spec) and is the
command an agent is told to run.
"""

from __future__ import annotations

from kernote.mcp.server import main

if __name__ == "__main__":
    main()
