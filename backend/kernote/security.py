"""Browser-borne attack surface of a server that has no login.

Kernote binds to 127.0.0.1 and has no authentication, because it is a
single-user local tool. That is only safe if a *web page you happen to have
open* cannot talk to it. Two ways it could:

**DNS rebinding.** `evil.example` resolves to the attacker, the page loads,
then the name is re-pointed at 127.0.0.1. The browser now treats requests to
the API as same-origin, so CORS never applies -- the page can read the whole
vault. The one thing that does not change is the `Host` header: it still says
`evil.example`. So: refuse any request whose Host is not a loopback name.

**Cross-site writes.** A page can POST to http://127.0.0.1 without reading the
reply. Browsers attach `Origin` to every such request, so: for anything that
changes state, a present Origin must itself be a loopback origin.

No cookies, tokens or CSRF secrets are needed; the browser does the work.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _hostname(value: str) -> str:
    """Hostname only, lower-cased, without port or IPv6 brackets."""
    host = urlsplit(f"//{value}").hostname
    return (host or "").lower()


def install_host_guard(app: FastAPI, allowed_hosts: tuple[str, ...]) -> None:
    allowed = frozenset(h.lower() for h in allowed_hosts)

    @app.middleware("http")
    async def _guard(request: Request, call_next):
        host = _hostname(request.headers.get("host", ""))
        if host not in allowed:
            return JSONResponse(
                status_code=403,
                content={"detail": f"host {host or '(none)'!r} is not allowed"},
            )
        if request.method not in _SAFE_METHODS:
            origin = request.headers.get("origin")
            # "null" (sandboxed iframes, file://) parses to no hostname and is
            # refused along with every foreign site.
            if origin is not None and _hostname(urlsplit(origin).netloc) not in allowed:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "cross-origin write refused"},
                )
        return await call_next(request)
