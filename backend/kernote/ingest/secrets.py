"""Content-level secret refusal (ADR-0013).

Path-based refusal in `walker.py` stops us opening `.env` or `id_rsa` at all.
This module is the second line: a credential pasted into a README that no
filename pattern would catch.

Why `detect_secrets.core.scan.scan_file` and not `scan_line`: `scan_line` is a
low-level primitive that bypasses detect-secrets' filters, so it reports
Base64/Hex "high entropy" hits on ordinary prose, on `pip install -r
requirements.txt`, and on `fastapi==0.115.6`. Wiring that in would have refused
essentially every file in every repository. `scan_file` applies the filter
chain and returned zero hits on a benign documentation fixture while catching a
GitHub token and an AWS key with correct line numbers.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import structlog
from detect_secrets.core import scan
from detect_secrets.settings import default_settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SecretHit:
    """A suspected credential. Deliberately carries no secret value.

    Only the location and the detector name are recorded, because this ends up
    in logs and in the review UI, and writing the credential there would
    recreate the leak we are refusing.
    """

    line_number: int
    detector: str


# Detectors that match a credential *format* and essentially do not misfire:
# a string shaped like a GitHub token is a GitHub token.
HIGH_PRECISION: frozenset[str] = frozenset(
    {
        "AWS Access Key",
        "Azure Storage Account access key",
        "Basic Auth Credentials",
        "Cloudant Credentials",
        "Discord Bot Token",
        "GitHub Token",
        "GitLab Token",
        "IBM COS HMAC Credentials",
        "IBM Cloud IAM Key",
        "JSON Web Token",
        "Mailchimp Access Key",
        "NPM tokens",
        "Private Key",
        "SendGrid API Key",
        "Slack Token",
        "Softlayer Credentials",
        "Square OAuth Secret",
        "Stripe Access Key",
        "Telegram Bot Token",
        "Twilio API Key",
    }
)

# Everything else -- "Secret Keyword", the entropy detectors -- is a guess.
# Dogfooding Kernote on its own repository refused `domain/models.py` because
# it contains `SECRET_SUSPECTED = "secret_suspected"`, and
# `screens/Dashboard.tsx` because it contains the words "possible secret".
# Any security-adjacent codebase would lose files to that. Low-precision hits
# therefore warn instead of refusing.


def classify(hits: list[SecretHit]) -> tuple[list[SecretHit], list[SecretHit]]:
    """Split hits into (refuse, warn).

    A format match refuses the file. A keyword or entropy guess does not,
    because the false-positive rate on real code is high enough to make the
    scanner useless -- see the dogfooding note above.
    """
    refuse = [h for h in hits if h.detector in HIGH_PRECISION]
    warn = [h for h in hits if h.detector not in HIGH_PRECISION]
    return refuse, warn


@contextlib.contextmanager
def scanning_session() -> Iterator[None]:
    """Load detect-secrets' default plugin and filter settings once per scan.

    Entering the settings context per file is measurable overhead on a few
    thousand files, so the pipeline wraps its whole loop in this.
    """
    with default_settings():
        yield


def scan_path(path: Path) -> list[SecretHit]:
    """Suspected secrets in one file. Requires an active `scanning_session()`.

    Returns an empty list when the file cannot be read: an unreadable file is
    the walker's problem to report, and guessing "no secrets" is the safe
    answer only because nothing will be stored from it either.
    """
    try:
        hits = list(scan.scan_file(str(path)))
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("secrets.unscannable", path=str(path), error=str(exc))
        return []
    return sorted(
        {SecretHit(h.line_number, h.type) for h in hits},
        key=lambda h: (h.line_number, h.detector),
    )
