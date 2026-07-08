"""Deterministic server-side banner fingerprinting.

The scan agent's nmap-service-probes matching identifies most services at the
edge. When it can't (an agent without nmap, or a plain connect scan), a raw
banner still often names the service outright: an SSH banner literally starts
with ``SSH-2.0-OpenSSH_9.6``. This module recognizes those common
self-announcing banners on the server with no LLM cost, so detection stays high
before falling back to (optional, slower) AI enrichment.

Matches are deliberately conservative. For an audit tool a wrong service label
is worse than "unknown", so a rule only fires on a distinctive leading token
(``SSH-``, ``220 ... ESMTP``, ``+OK``, a ``Server:`` header, ...), and product
and version are filled only when a clear pattern is present.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A clear self-announcing banner is very reliable, but we keep it just below a
# full nmap probe match so provenance still favors the agent's deterministic
# fingerprint when both are available for the same port.
HEURISTIC_CONFIDENCE = 0.85

# A dotted numeric version, optionally with a short suffix like "p1" or "0rc2".
# Deliberately excludes '-'/'+' so package suffixes (e.g. "-1ubuntu2") are not
# folded into the version we report.
_VERSION = r"(?P<version>\d+(?:\.\d+)+[A-Za-z0-9._]*)"


@dataclass(frozen=True)
class FingerprintMatch:
    service: str
    product: str | None = None
    version: str | None = None
    confidence: float = HEURISTIC_CONFIDENCE


@dataclass(frozen=True)
class _Rule:
    service: str
    detect: re.Pattern[str]
    # Product/version extractors tried in order; the first match wins.
    products: tuple[re.Pattern[str], ...] = ()


def _p(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_RULES: tuple[_Rule, ...] = (
    _Rule(
        "ssh",
        _p(r"^SSH-\d+\.\d+-"),
        (
            _p(rf"(?P<product>OpenSSH)[_/ ]{_VERSION}"),
            _p(rf"(?P<product>Dropbear)(?:[_ ]?sshd?)?[_ ]{_VERSION}"),
        ),
    ),
    _Rule(
        "smtp",
        _p(r"^220\b.*\b(?:ESMTP|SMTP)\b"),
        (
            _p(rf"(?P<product>Exim)\s+{_VERSION}"),
            _p(rf"(?P<product>Sendmail)\s+{_VERSION}"),
            _p(r"(?P<product>Postfix)"),
            _p(r"(?P<product>Microsoft ESMTP MAIL Service)"),
        ),
    ),
    _Rule(
        "ftp",
        _p(r"^220\b.*(?:FTP|ftpd|FileZilla)"),
        (
            _p(rf"(?P<product>vsFTPd)\s*{_VERSION}"),
            _p(rf"(?P<product>ProFTPD)\s*{_VERSION}"),
            _p(rf"(?P<product>FileZilla Server)\s*{_VERSION}"),
            _p(r"(?P<product>Pure-FTPd)"),
        ),
    ),
    _Rule(
        "imap",
        _p(r"^\*\s+OK\b.*(?:IMAP|Dovecot)"),
        (_p(r"(?P<product>Dovecot)"),),
    ),
    _Rule(
        "pop3",
        _p(r"^\+OK\b.*(?:POP3|Dovecot)"),
        (_p(r"(?P<product>Dovecot)"),),
    ),
    _Rule(
        "http",
        _p(r"^HTTP/\d|\bServer:\s*\S"),
        (
            _p(rf"Server:\s*(?P<product>nginx)/{_VERSION}"),
            _p(rf"Server:\s*(?P<product>Apache)(?:/{_VERSION})?"),
            _p(rf"Server:\s*(?P<product>Microsoft-IIS)/{_VERSION}"),
            _p(rf"Server:\s*(?P<product>lighttpd)/{_VERSION}"),
            _p(rf"Server:\s*(?P<product>[\w.-]+)/{_VERSION}"),
        ),
    ),
)


def match_banner(banner: str | None) -> FingerprintMatch | None:
    """Identify a service from a raw banner via distinctive self-announcing
    tokens. Returns ``None`` when nothing matches confidently."""
    if not banner:
        return None
    text = banner.strip()
    if not text:
        return None
    for rule in _RULES:
        if not rule.detect.search(text):
            continue
        product: str | None = None
        version: str | None = None
        for prod_re in rule.products:
            m = prod_re.search(text)
            if m:
                product = m.group("product")
                version = m.groupdict().get("version")
                break
        return FingerprintMatch(rule.service, product, version)
    return None
