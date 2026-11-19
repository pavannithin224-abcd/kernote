"""The desktop window, minus the window.

The GUI itself cannot be asserted in a test suite, and pretending otherwise
would be worse than not testing it. What *is* testable is everything around
it, which is where this would actually fail a user: refusing to open a window
onto a dead port, noticing an instance already running, and degrading with an
explanation when the machine has no webview rather than dying in the GUI
layer.
"""

from __future__ import annotations

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from kernote import desktop


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_port_is_free_tracks_reality():
    port = _free_port()
    assert desktop.port_is_free("127.0.0.1", port)

    with socket.socket() as holder:
        holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        holder.bind(("127.0.0.1", port))
        holder.listen(1)
        assert not desktop.port_is_free("127.0.0.1", port)


def test_wait_until_ready_returns_false_for_a_dead_port():
    """The window must never open onto nothing.

    An empty webview with no explanation is worse than a terminal line
    saying what went wrong.
    """
    started = time.monotonic()
    assert (
        desktop.wait_until_ready(f"http://127.0.0.1:{_free_port()}/health", timeout=0.6)
        is False
    )
    assert time.monotonic() - started < 5, "it should give up at the timeout, not hang"


def test_wait_until_ready_sees_a_live_server():
    port = _free_port()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert desktop.wait_until_ready(f"http://127.0.0.1:{port}/health", timeout=5.0) is True
    finally:
        server.shutdown()


def test_a_missing_pywebview_explains_itself(monkeypatch):
    """Not an ImportError traceback: an instruction."""
    import builtins

    real_import = builtins.__import__

    def no_webview(name, *args, **kwargs):
        if name == "webview":
            raise ImportError("no module named webview")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_webview)
    reason = desktop.gui_unavailable_reason()
    assert reason is not None
    assert "requirements-desktop.txt" in reason


def test_an_unbuilt_ui_is_refused_with_the_build_command(monkeypatch, capsys):
    monkeypatch.setattr(desktop, "web_dist", lambda: None)
    assert desktop.main() == 1
    assert "npm --prefix frontend run build" in capsys.readouterr().out


def test_a_busy_port_that_is_not_kernote_is_reported(monkeypatch, capsys):
    """Starting a second copy on top of a stranger's port would be worse."""
    monkeypatch.setattr(desktop, "web_dist", lambda: "dist")
    monkeypatch.setattr(desktop, "gui_unavailable_reason", lambda: None)
    monkeypatch.setattr(desktop, "port_is_free", lambda *a: False)
    monkeypatch.setattr(desktop, "wait_until_ready", lambda *a, **k: False)

    assert desktop.main() == 1
    assert "is in use by something that is not Kernote" in capsys.readouterr().out


def test_an_already_running_kernote_is_reused_not_restarted(monkeypatch, capsys):
    monkeypatch.setattr(desktop, "web_dist", lambda: "dist")
    monkeypatch.setattr(desktop, "gui_unavailable_reason", lambda: "no webview here")
    monkeypatch.setattr(desktop, "port_is_free", lambda *a: False)
    monkeypatch.setattr(desktop, "wait_until_ready", lambda *a, **k: True)

    assert desktop.main() == 0
    out = capsys.readouterr().out
    assert "already running" in out
    assert "no webview here" in out


def test_no_webview_still_serves_rather_than_refusing(monkeypatch, capsys):
    """Degrading, not failing: the product works fine in a browser."""
    monkeypatch.setattr(desktop, "web_dist", lambda: "dist")
    monkeypatch.setattr(desktop, "gui_unavailable_reason", lambda: "apt install something")
    monkeypatch.setattr(desktop, "port_is_free", lambda *a: True)
    monkeypatch.setattr(desktop, "_serve", lambda host, port: None)
    monkeypatch.setattr(desktop, "wait_until_ready", lambda *a, **k: True)

    def interrupt(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(desktop.time, "sleep", interrupt)

    assert desktop.main() == 0
    out = capsys.readouterr().out
    assert "apt install something" in out
    assert "Serving in the terminal instead" in out


def test_a_server_that_never_comes_up_does_not_open_a_window(monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(desktop, "web_dist", lambda: "dist")
    monkeypatch.setattr(desktop, "gui_unavailable_reason", lambda: None)
    monkeypatch.setattr(desktop, "port_is_free", lambda *a: True)
    monkeypatch.setattr(desktop, "_serve", lambda host, port: None)
    monkeypatch.setattr(desktop, "wait_until_ready", lambda *a, **k: False)
    monkeypatch.setattr(desktop, "_open_window", lambda url: opened.append(url))

    assert desktop.main() == 1
    assert opened == [], "a window was opened onto a server that never started"
    assert "did not become ready" in capsys.readouterr().out


@pytest.mark.parametrize("ready", [True, False])
def test_the_window_opens_only_when_the_server_answers(monkeypatch, ready):
    opened = []
    monkeypatch.setattr(desktop, "web_dist", lambda: "dist")
    monkeypatch.setattr(desktop, "gui_unavailable_reason", lambda: None)
    monkeypatch.setattr(desktop, "port_is_free", lambda *a: True)
    monkeypatch.setattr(desktop, "_serve", lambda host, port: None)
    monkeypatch.setattr(desktop, "wait_until_ready", lambda *a, **k: ready)
    monkeypatch.setattr(desktop, "_open_window", lambda url: opened.append(url))

    desktop.main()
    assert bool(opened) is ready


def test_window_fits_a_small_display():
    # 1366x768 laptop, and 125%-scaled 1920x1080 (= 1536x864 effective).
    assert desktop.window_size((1366, 768)) == (1286, 628)
    assert desktop.window_size((1536, 864)) == (1366, 724)


def test_window_never_exceeds_the_default_on_a_big_display():
    assert desktop.window_size((3840, 2160)) == desktop.DEFAULT_SIZE


def test_window_never_goes_below_the_designed_minimum():
    assert desktop.window_size((800, 500)) == desktop.MIN_SIZE


def test_window_size_with_unknown_display_uses_the_default():
    assert desktop.window_size(None) == desktop.DEFAULT_SIZE
