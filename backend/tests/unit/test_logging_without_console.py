"""A windowed build has no console, so `sys.stderr` is None.

That used to kill the process on the first log line, silently: a double-clicked
app that never appears and leaves nothing to read. Logs must land in a file.
"""

from __future__ import annotations

import sys

import structlog

from kernote import logging as klog
from kernote.config import settings


def test_logging_survives_missing_stderr_and_writes_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(klog, "_log_file", None)
    monkeypatch.setattr(sys, "stderr", None)

    klog.configure_logging(force=True)
    structlog.get_logger().info("windowed.probe", marker="no-console")

    handle = klog._log_file
    assert handle is not None
    handle.flush()
    text = (tmp_path / "logs" / "kernote.log").read_text(encoding="utf-8")
    assert "windowed.probe" in text and "no-console" in text
    handle.close()
    klog.configure_logging(force=True)  # restore a normal sink for later tests
