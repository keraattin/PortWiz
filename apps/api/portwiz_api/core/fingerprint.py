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


# The registered service for a well-known (port, protocol). Used only as a last
# resort when neither the agent's nmap probe nor a banner identified the service:
# an open port on a well-known number is very likely its registered service
# (3306 -> mysql, 6379 -> redis). It is a guess *by port number*, so it carries a
# low confidence and never overrides an observed fingerprint; it just turns
# "unknown" into the likely service for the common ports that make up most
# exposure. Kept conservative and canonical (nmap service names) so a wrong label
# is unlikely for an audit tool.
PORT_MAP_CONFIDENCE = 0.4

_WELL_KNOWN_PORTS: dict[tuple[int, str], str] = {
    (21, "tcp"): "ftp",
    (22, "tcp"): "ssh",
    (23, "tcp"): "telnet",
    (25, "tcp"): "smtp",
    (53, "tcp"): "dns",
    (53, "udp"): "dns",
    (67, "udp"): "dhcp",
    (69, "udp"): "tftp",
    (80, "tcp"): "http",
    (88, "tcp"): "kerberos",
    (110, "tcp"): "pop3",
    (111, "tcp"): "rpcbind",
    (123, "udp"): "ntp",
    (135, "tcp"): "msrpc",
    (139, "tcp"): "netbios-ssn",
    (143, "tcp"): "imap",
    (161, "udp"): "snmp",
    (179, "tcp"): "bgp",
    (389, "tcp"): "ldap",
    (443, "tcp"): "https",
    (445, "tcp"): "microsoft-ds",
    (465, "tcp"): "smtps",
    (500, "udp"): "isakmp",
    (514, "udp"): "syslog",
    (587, "tcp"): "submission",
    (631, "tcp"): "ipp",
    (636, "tcp"): "ldaps",
    (993, "tcp"): "imaps",
    (995, "tcp"): "pop3s",
    (1080, "tcp"): "socks",
    (1194, "udp"): "openvpn",
    (1433, "tcp"): "ms-sql-s",
    (1521, "tcp"): "oracle",
    (1723, "tcp"): "pptp",
    (2049, "tcp"): "nfs",
    (2181, "tcp"): "zookeeper",
    (2375, "tcp"): "docker",
    (2376, "tcp"): "docker-ssl",
    (2379, "tcp"): "etcd",
    (3306, "tcp"): "mysql",
    (3389, "tcp"): "ms-wbt-server",
    (3690, "tcp"): "svn",
    (5060, "tcp"): "sip",
    (5060, "udp"): "sip",
    (5222, "tcp"): "xmpp-client",
    (5432, "tcp"): "postgresql",
    (5601, "tcp"): "kibana",
    (5672, "tcp"): "amqp",
    (5900, "tcp"): "vnc",
    (5984, "tcp"): "couchdb",
    (6379, "tcp"): "redis",
    (6443, "tcp"): "kubernetes-api",
    (8080, "tcp"): "http-proxy",
    (8086, "tcp"): "influxdb",
    (8443, "tcp"): "https-alt",
    (9042, "tcp"): "cassandra",
    (9092, "tcp"): "kafka",
    (9200, "tcp"): "elasticsearch",
    (11211, "tcp"): "memcached",
    (15672, "tcp"): "rabbitmq-management",
    (27017, "tcp"): "mongodb",
}


def service_for_port(port: int, protocol: str | None) -> str | None:
    """The registered service for a well-known (port, protocol), or ``None``.

    A guess by port number only: use it as a last resort when nothing observed
    the service, never to override a real fingerprint."""
    proto = (protocol or "tcp").strip().lower()
    return _WELL_KNOWN_PORTS.get((port, proto))


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
