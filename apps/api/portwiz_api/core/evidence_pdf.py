"""Render an evidence package to an auditor-friendly PDF (reportlab)."""

from __future__ import annotations

import datetime as dt
import io
from enum import Enum
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.evidence import EvidencePackage

_TEAL = colors.HexColor("#0f766e")
_INK = colors.HexColor("#0f172a")
_MUTED = colors.HexColor("#475569")
_GRID = colors.HexColor("#cbd5e1")
_ZEBRA = colors.HexColor("#f1f5f9")

_styles = getSampleStyleSheet()
_cell = ParagraphStyle("cell", parent=_styles["BodyText"], fontSize=8, leading=10)
_cell_head = ParagraphStyle(
    "cellhead", parent=_cell, textColor=colors.white, fontName="Helvetica-Bold"
)
_title = ParagraphStyle("title", parent=_styles["Title"], fontSize=18, textColor=_TEAL)
_h2 = ParagraphStyle("h2", parent=_styles["Heading2"], fontSize=12, textColor=_INK)
_meta = ParagraphStyle("meta", parent=_styles["BodyText"], fontSize=9, textColor=_MUTED)


def _ev(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _fmt(value: dt.datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else "-"


def _snapshot(snap: dict) -> str:
    if snap.get("state") == "open":
        detail = " ".join(x for x in [snap.get("service"), snap.get("version")] if x)
        return f"open ({detail})" if detail else "open"
    return "closed"


def _p(text: Any, head: bool = False) -> Paragraph:
    return Paragraph(_ev(text), _cell_head if head else _cell)


def _table(header: list[str], rows: list[list[Any]], col_widths: list[float]) -> Table:
    data = [[_p(h, head=True) for h in header]]
    data += [[_p(cell) for cell in row] for row in rows]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _TEAL),
                ("GRID", (0, 0), (-1, -1), 0.25, _GRID),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ZEBRA]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def render_evidence_pdf(pkg: EvidencePackage) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        title="PortWiz Evidence Package",
    )

    chain = pkg.chain_verification
    chain_color = "#059669" if chain.ok else "#dc2626"
    chain_text = "INTACT" if chain.ok else f"BROKEN at seq {chain.broken_seq}"

    story: list[Any] = [
        Paragraph("PortWiz Evidence Package", _title),
        Paragraph(f"Scan profile: <b>{pkg.profile.name}</b>", _meta),
        Paragraph(f"Generated {_fmt(pkg.generated_at)} by {pkg.generated_by}", _meta),
        Paragraph(
            f'Audit chain integrity: <font color="{chain_color}"><b>{chain_text}</b></font>'
            f" ({chain.total} total events)",
            _meta,
        ),
        Spacer(1, 8),
        Paragraph("Profile", _h2),
        _table(
            ["Field", "Value"],
            [
                ["Targets", ", ".join(pkg.profile.targets)],
                ["Ports", pkg.profile.ports],
                ["Scan type", _ev(pkg.profile.scan_type)],
                ["Scan source", _ev(pkg.profile.scan_source)],
            ],
            [40 * mm, 140 * mm],
        ),
        Spacer(1, 8),
        Paragraph(f"Current exposure ({len(pkg.current_open_ports)} open ports)", _h2),
    ]

    if pkg.current_open_ports:
        story.append(
            _table(
                ["Host", "Port", "Proto", "Service", "Version"],
                [
                    [o.ip, o.port, o.protocol, o.service or "-", o.version or "-"]
                    for o in pkg.current_open_ports
                ],
                [45 * mm, 20 * mm, 20 * mm, 45 * mm, 50 * mm],
            )
        )
    else:
        story.append(Paragraph("No open ports.", _meta))

    story += [
        Spacer(1, 8),
        Paragraph(f"Known vulnerabilities ({len(pkg.cve_findings)})", _h2),
    ]
    if pkg.cve_findings:
        story.append(
            _table(
                ["Host:Port", "CVE", "CVSS", "Severity", "Summary"],
                [
                    [
                        f"{f.ip}:{f.port}",
                        f.cve_id,
                        "-" if f.cvss is None else f"{f.cvss:.1f}",
                        f.severity,
                        f.summary or "-",
                    ]
                    for f in pkg.cve_findings
                ],
                [30 * mm, 32 * mm, 15 * mm, 20 * mm, 83 * mm],
            )
        )
    else:
        story.append(Paragraph("No known vulnerabilities recorded.", _meta))

    story += [Spacer(1, 8), Paragraph(f"Confirmed changes ({len(pkg.changes)})", _h2)]
    if pkg.changes:
        story.append(
            _table(
                ["Type", "Host:Port", "Before", "After", "Severity", "Status", "Detected"],
                [
                    [
                        c.change_type,
                        f"{c.ip}:{c.port}/{c.protocol}",
                        _snapshot(c.before),
                        _snapshot(c.after),
                        c.severity,
                        c.status,
                        _fmt(c.detected_at),
                    ]
                    for c in pkg.changes
                ],
                [22 * mm, 30 * mm, 28 * mm, 28 * mm, 18 * mm, 22 * mm, 32 * mm],
            )
        )
    else:
        story.append(Paragraph("No confirmed changes.", _meta))

    story += [Spacer(1, 8), Paragraph(f"Scan runs ({len(pkg.scan_runs)})", _h2)]
    if pkg.scan_runs:
        story.append(
            _table(
                ["Status", "Source", "Started", "Finished"],
                [
                    [_ev(r.status), _ev(r.scan_source), _fmt(r.started_at), _fmt(r.finished_at)]
                    for r in pkg.scan_runs
                ],
                [25 * mm, 45 * mm, 55 * mm, 55 * mm],
            )
        )

    story += [Spacer(1, 8), Paragraph(f"Audit log slice ({len(pkg.audit_slice)} events)", _h2)]
    if pkg.audit_slice:
        story.append(
            _table(
                ["Seq", "Action", "Actor", "Target", "Time"],
                [
                    [
                        a.seq,
                        a.action,
                        a.actor_email or "-",
                        f"{a.target_type or '-'}:{(a.target_id or '')[:8]}",
                        _fmt(a.created_at),
                    ]
                    for a in pkg.audit_slice
                ],
                [15 * mm, 45 * mm, 45 * mm, 35 * mm, 40 * mm],
            )
        )

    doc.build(story)
    return buffer.getvalue()
