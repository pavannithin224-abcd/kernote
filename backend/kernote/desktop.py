"""Run Kernote in its own window.

The API already serves the built UI from one process, so a desktop window is
a thin thing: start that server on a background thread and point the
operating system's webview at it. No second process, no sidecar to supervise,
no bundled browser (ADR-0042).

**It degrades instead of failing.** A platform webview is present by default
on Windows and macOS, but on Linux it is a system package that may be
missing, and a headless machine has no display at all. In either case this
keeps serving and says where to point a browser, because being unable to open
a window is not a reason to refuse to run.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import structlog
import uvicorn

from .config import settings
from .main import app as api_app
from .main import web_dist

log = structlog.get_logger(__name__)

WINDOW_TITLE = "Kernote"
READY_TIMEOUT = 20.0


def port_is_free(host: str, port: int) -> bool:
    """Whether we can bind, used to tell "already running" from "broken"."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform == "win32":
            # On Windows SO_REUSEADDR lets a second socket bind a port that is
            # already *listening* (it is not the POSIX TIME_WAIT-only option),
            # so the probe would report a busy port as free. Exclusive use
            # makes bind() fail whenever anything else holds the port.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def wait_until_ready(url: str, timeout: float = READY_TIMEOUT) -> bool:
    """Poll /health until the server answers.

    The window must not open on a dead port: an empty webview with no
    explanation is worse than a terminal line saying what went wrong.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:  # noqa: S310
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.15)
    return False


def gui_unavailable_reason() -> str | None:
    """Why a window cannot be opened here, or None if one can.

    Checked before starting anything, so the fallback message arrives
    immediately rather than after a stack trace from inside the GUI layer.
    """
    try:
        import webview  # noqa: F401
    except ImportError:
        return (
            "pywebview is not installed. Install it with:\n"
            "  backend/.venv/bin/pip install -r backend/requirements-desktop.txt"
        )

    import platform

    if platform.system() == "Linux":
        try:
            import gi

            gi.require_version("WebKit2", "4.1")
        except (ImportError, ValueError):
            try:
                import PyQt6.QtWebEngineWidgets  # noqa: F401
            except ImportError:
                return (
                    "no platform webview found. On Debian/Ubuntu:\n"
                    "  sudo apt install gir1.2-webkit2-4.1"
                )
    return None


def _serve(host: str, port: int) -> threading.Thread:
    """Run the API on a daemon thread, so closing the window ends the process."""
    # The module-level app, the same object `uvicorn kernote.main:app` runs.
    # Calling create_app() again would build a second one and scan the build
    # directory twice, which showed up as a duplicated "web.serving" line.
    config = uvicorn.Config(api_app, host=host, port=port, log_config=None)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="kernote-api", daemon=True)
    thread.start()
    return thread


def _say(message: str) -> None:
    """Tell the user something, whether or not there is a console.

    A windowed build has no stdout, so a bare print() is invisible and a
    failure looks like "I double-clicked and nothing happened". On Windows
    the message goes to a native dialog as well, and always to the log.
    """
    print(message)
    log.warning("desktop.notice", message=message)
    if sys.platform == "win32" and sys.stdout is None:
        import ctypes

        # MB_OK | MB_ICONINFORMATION | MB_TOPMOST
        ctypes.windll.user32.MessageBoxW(None, message, WINDOW_TITLE, 0x40 | 0x40000)


def main() -> int:
    host, port = settings.host, settings.port
    url = f"http://{host}:{port}"

    if web_dist() is None:
        _say("The UI has not been built. Run:\n  npm --prefix frontend run build")
        return 1

    reason = gui_unavailable_reason()

    if not port_is_free(host, port):
        # Something already holds the port. Most likely Kernote itself, so
        # point at it rather than starting a second copy on top.
        if wait_until_ready(f"{url}/health", timeout=2.0):
            print(f"Kernote is already running at {url}")
            if reason is None:
                _open_window(url)
                return 0
            _say(reason)
            return 0
        _say(f"Port {port} is in use by something that is not Kernote.")
        return 1

    _serve(host, port)
    if not wait_until_ready(f"{url}/health"):
        _say(f"The API did not become ready within {READY_TIMEOUT:.0f}s.")
        return 1

    if reason is not None:
        # Serving anyway: a missing window is not a reason to refuse to run.
        _say(f"{reason}\n\nServing in the terminal instead: {url}\nCtrl-C to stop.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0

    _open_window(url)
    return 0


def _open_window(url: str) -> None:
    import webview

    log.info("desktop.window", url=url)
    webview.create_window(WINDOW_TITLE, url, width=1366, height=900, min_size=(960, 600))
    # Blocks until the window is closed; the API thread is a daemon, so the
    # process ends with it.
    webview.start()


if __name__ == "__main__":
    raise SystemExit(main())
