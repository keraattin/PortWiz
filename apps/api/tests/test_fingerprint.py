"""Deterministic server-side banner fingerprinting.

``match_banner`` recognizes common self-announcing banners with no LLM cost.
It must stay conservative: distinctive banners resolve to the right service
(with product/version where present), and anything unrecognized returns None.
"""

from __future__ import annotations

import pytest

from portwiz_api.core.fingerprint import HEURISTIC_CONFIDENCE, match_banner


@pytest.mark.parametrize(
    ("banner", "service", "product", "version"),
    [
        ("SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5", "ssh", "OpenSSH", "9.6p1"),
        ("SSH-2.0-OpenSSH_8.9", "ssh", "OpenSSH", "8.9"),
        ("SSH-2.0-dropbear_2022.83", "ssh", "dropbear", "2022.83"),
        ("SSH-1.99-Cisco-1.25", "ssh", None, None),  # ssh, unknown product
        ("220 mail.example.com ESMTP Postfix (Ubuntu)", "smtp", "Postfix", None),
        ("220 relay ESMTP Exim 4.94.2 Mon, 01 Jan 2026", "smtp", "Exim", "4.94.2"),
        ("220 (vsFTPd 3.0.5)", "ftp", "vsFTPd", "3.0.5"),
        ("220 ProFTPD 1.3.8 Server ready", "ftp", "ProFTPD", "1.3.8"),
        ("+OK Dovecot ready.", "pop3", "Dovecot", None),
        ("* OK [CAPABILITY IMAP4rev1] Dovecot ready.", "imap", "Dovecot", None),
        (
            "HTTP/1.1 200 OK\r\nServer: nginx/1.24.0\r\nDate: x",
            "http",
            "nginx",
            "1.24.0",
        ),
        (
            "HTTP/1.1 403 Forbidden\r\nServer: Apache/2.4.52 (Ubuntu)\r\n",
            "http",
            "Apache",
            "2.4.52",
        ),
    ],
)
def test_match_banner_recognizes(banner, service, product, version) -> None:
    match = match_banner(banner)
    assert match is not None
    assert match.service == service
    assert match.product == product
    assert match.version == version
    assert match.confidence == HEURISTIC_CONFIDENCE


@pytest.mark.parametrize(
    "banner",
    [
        None,
        "",
        "   ",
        "ACME Appliance ready v2.1",  # custom, no distinctive token
        "some random bytes \x00\x01",
        "220",  # bare code, no service token
    ],
)
def test_match_banner_ignores_unknown(banner) -> None:
    assert match_banner(banner) is None


def test_smtp_wins_over_ftp_for_esmtp_banner() -> None:
    # A "220 ... ESMTP" banner is SMTP even though both rules key on "220".
    match = match_banner("220 host.example.com ESMTP ready")
    assert match is not None
    assert match.service == "smtp"
