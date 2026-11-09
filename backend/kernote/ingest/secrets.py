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
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import structlog
from detect_secrets.core import scan
from detect_secrets.settings import default_settings

log = structlog.get_logger(__name__)


# A keyword hit says the *name* looks like a credential. These decide whether
# the *value* does, which is the part that matters. Without this,
# `DB_PASSWORD = "Tr0ub4dor&3xKq9vZ"` was only warned about and stored, while
# `SECRET_SUSPECTED = "secret_suspected"` was refused -- exactly backwards.
_QUOTED = re.compile(r"""['"]([^'"\n]{0,200})['"]""")
_PLACEHOLDER = re.compile(
    r"^(?:your[-_ ]|my[-_ ]|some[-_ ]|an?[-_ ])|"
    r"(?:example|placeholder|changeme|change[-_ ]me|redacted|removed|todo|fixme|"
    r"xxx+|\.\.\.|dummy|sample|test|fake|none|null|undefined|insert|replace)",
    re.IGNORECASE,
)
_TEMPLATE = re.compile(r"\$\{|\{\{|<[^>]{1,40}>|%\(|%s\b|\$[A-Z_]{3,}", re.IGNORECASE)
# A value read from the environment or a config object is a reference, not a
# literal. `PASSWORD = os.environ["DB_PASSWORD"]` quotes a *key name*.
_INDIRECTION = re.compile(
    r"\b(?:environ|getenv|env\.|process\.env|config(?:\.|\[)|settings(?:\.|\[)|"
    r"secret(?:s)?(?:manager)?\.(?:get|fetch)|vault\.|keyring\.|"
    r"get_secret|read_secret|lookup)",
    re.IGNORECASE,
)
# The key is whatever precedes the first assignment separator, `=` or `:`.
_ASSIGN = re.compile(r"[:=]")
_WORDS = re.compile(r"[^a-z0-9]+")
# Word count outside the quoted literal, above which a line reads as prose
# rather than as an assignment.
_PROSE_WORD_LIMIT = 8

# Key names that actually announce a credential. A high-entropy value proves
# nothing on its own -- a SHA-256 digest, a UUID, a git object id and an API
# token are the same shape -- so for a low-precision hit the *name* has to
# carry the signal. Scanning a real data-heavy repository showed what the
# alternative costs: 2918 of 2938 files refused, including three of the
# repository's seven Markdown documents, because every hash in a JSON
# manifest is twenty-plus characters without a space (ADR-0020c).
_CREDENTIAL_KEY = re.compile(
    r"(?:^|[^a-z])(?:"
    r"pass(?:wd|word)?|pwd|secret|token|api[_-]?key|auth|credential|"
    r"bearer|private[_-]?key|access[_-]?key|client[_-]?secret|"
    r"session[_-]?key|encryption[_-]?key|signing[_-]?key|salt|"
    r"connection[_-]?string|dsn"
    r")(?:[^a-z]|$)",
    re.IGNORECASE,
)


def key_names_a_credential(line: str) -> bool:
    """Does the *name* being assigned on this line announce a credential?

    Checked against the text before the first `=` or `:`, so a value that
    merely contains the word "token" does not make its own key suspicious.
    """
    head = _ASSIGN.split(line, 1)[0]
    return _CREDENTIAL_KEY.search(head) is not None


def _char_classes(value: str) -> int:
    return sum(
        (
            any(c.islower() for c in value),
            any(c.isupper() for c in value),
            any(c.isdigit() for c in value),
            any(not c.isalnum() for c in value),
        )
    )


def value_looks_like_credential(line: str) -> bool:
    """Does the assigned value on this line look like an actual secret?

    Deliberately conservative in the *safe* direction: anything that plausibly
    looks like a credential refuses the file. The cases it must NOT flag are
    the ones dogfooding found -- a value that merely restates its own key, a
    placeholder, or prose.
    """
    if _INDIRECTION.search(line):
        return False
    # A credential assignment is terse: `DB_PASSWORD = "..."` is three tokens.
    # A sentence *about* credentials is not. Without this, documentation that
    # discusses secret handling is refused for containing an example -- it
    # cost us `docs/DECISIONS.md` and 23 decision memories, and it would cost
    # every project that documents its own security decisions.
    outside_quotes = _QUOTED.sub(" ", line)
    if len(outside_quotes.split()) >= _PROSE_WORD_LIMIT:
        return False
    # Split on `=` or `:` so YAML-style `password: '...'` is handled too; using
    # `=` alone made the whole line the "key", so the value always looked
    # self-referential and a real secret was missed.
    head = _ASSIGN.split(line, 1)[0]
    key_words = set(_WORDS.split(head.lower())) - {""}
    for raw in _QUOTED.findall(line):
        value = raw.strip().strip("<>")
        if len(value) < 8:
            continue
        if " " in value or "\t" in value:
            continue  # prose, not a credential
        if _PLACEHOLDER.search(value) or _TEMPLATE.search(raw):
            continue
        # `SECRET_SUSPECTED = "secret_suspected"`: the value just restates the
        # key, which no real credential does.
        value_words = set(_WORDS.split(value.lower())) - {""}
        if value_words and value_words <= key_words:
            continue
        if _char_classes(value) >= 2 or len(value) >= 20:
            return True
    return False


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


def classify(
    hits: list[SecretHit], lines: list[str] | None = None
) -> tuple[list[SecretHit], list[SecretHit]]:
    """Split hits into (refuse, warn).

    Three rules, in order:

    1. A credential *format* match refuses the file outright.
    2. A keyword or entropy hit refuses it only when the line's **key names a
       credential** *and* the value is shaped like one. Both halves are
       required because each detector only knows half the story: the keyword
       detector knows the name looks secret and needs the value to confirm it,
       while an entropy detector knows the value is random and needs the name
       -- a digest, a UUID, a git object id and an API token are
       indistinguishable by shape. This is what still stops a real
       `DB_PASSWORD = "..."` being stored.
    3. Otherwise it only warns, because the keyword detector fires on the name
       alone and would lose ordinary files in any security-adjacent codebase.

    `lines` is optional so a caller with hits but no source can still get rule
    1; without it, rule 2 cannot be evaluated and those hits only warn.
    """
    refuse: list[SecretHit] = []
    warn: list[SecretHit] = []
    for hit in hits:
        if hit.detector in HIGH_PRECISION:
            refuse.append(hit)
            continue
        line = ""
        if lines and 1 <= hit.line_number <= len(lines):
            line = lines[hit.line_number - 1]
        if line and key_names_a_credential(line) and value_looks_like_credential(line):
            refuse.append(hit)
        else:
            warn.append(hit)
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


def read_lines(path: Path) -> list[str]:
    """Source lines for value-shape evaluation, or empty if unreadable."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
