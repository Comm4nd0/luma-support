"""Monthly client PDF report builder.

Generates a one-page-ish PDF summarising tickets opened/resolved, hours
logged, SLA compliance, and CSAT for a single client over a calendar
month. Output is bytes so the Celery task can attach it directly to an
EmailMessage without writing to disk.
"""
from __future__ import annotations

from datetime import datetime, timezone as _tz
from decimal import Decimal
from io import BytesIO
from typing import Optional

from django.db.models import Avg, Q, Sum
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_BRAND_NAVY = colors.HexColor("#0f172a")
_BRAND_TEAL = colors.HexColor("#14b8a6")
_BRAND_TEAL_DARK = colors.HexColor("#0f766e")


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=_tz.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=_tz.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=_tz.utc)
    return start, end


def build_monthly_report_pdf(client, year: int, month: int) -> bytes:
    """Render the PDF for `client` covering the calendar month `year`/`month`."""
    from tickets.models import CsatResponse, TimeEntry

    start, end = _month_bounds(year, month)

    opened = client.tickets.filter(created_at__gte=start, created_at__lt=end).count()
    resolved_qs = client.tickets.filter(
        resolved_at__gte=start, resolved_at__lt=end
    )
    resolved = resolved_qs.count()

    on_time = sum(
        1
        for t in resolved_qs
        if t.sla_deadline and t.resolved_at and t.resolved_at <= t.sla_deadline
    )
    sla_pct: Optional[float] = (on_time / resolved * 100) if resolved else None

    total_minutes = (
        TimeEntry.objects.filter(
            ticket__client=client,
            created_at__gte=start,
            created_at__lt=end,
        ).aggregate(t=Sum("minutes"))["t"]
        or 0
    )
    hours = (Decimal(total_minutes) / Decimal(60)).quantize(Decimal("0.1"))

    csat_qs = CsatResponse.objects.filter(
        ticket__client=client,
        responded_at__gte=start,
        responded_at__lt=end,
        rating__isnull=False,
    )
    csat_avg = csat_qs.aggregate(a=Avg("rating"))["a"]
    csat_count = csat_qs.count()

    # Build the document
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=f"Luma Tech Solutions — {client.name} — {start:%B %Y}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1",
        parent=styles["Title"],
        textColor=_BRAND_TEAL_DARK,
        spaceAfter=2,
    )
    h2 = ParagraphStyle(
        "h2",
        parent=styles["Heading2"],
        textColor=_BRAND_NAVY,
        spaceAfter=4,
    )
    body = styles["BodyText"]

    flow = [
        Paragraph("Luma Tech Solutions", h1),
        Paragraph(f"Monthly support report — {client.name}", h2),
        Paragraph(start.strftime("%B %Y"), body),
        Spacer(1, 6 * mm),
    ]

    summary_rows = [
        ["Metric", "Value"],
        ["Tickets opened", str(opened)],
        ["Tickets resolved", str(resolved)],
        ["Hours logged", f"{hours}"],
        [
            "SLA compliance",
            f"{sla_pct:.0f}%" if sla_pct is not None else "—",
        ],
        [
            "Customer satisfaction",
            f"{csat_avg:.1f} / 5  ({csat_count} responses)"
            if csat_avg
            else "—",
        ],
    ]
    summary = Table(summary_rows, colWidths=[70 * mm, 90 * mm])
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BRAND_NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f1f5f9")],
                ),
            ]
        )
    )
    flow.append(summary)
    flow.append(Spacer(1, 10 * mm))

    # Per-ticket detail
    ticket_qs = (
        client.tickets.filter(
            Q(created_at__gte=start, created_at__lt=end)
            | Q(resolved_at__gte=start, resolved_at__lt=end)
        )
        .distinct()
        .order_by("created_at")[:50]
    )
    ticket_rows = [["#", "Subject", "Priority", "Status", "Hours"]]
    for t in ticket_qs:
        mins = (
            t.time_entries.filter(created_at__gte=start, created_at__lt=end)
            .aggregate(t=Sum("minutes"))["t"]
            or 0
        )
        ticket_rows.append(
            [
                f"#{t.pk}",
                t.subject[:42],
                t.get_priority_display(),
                t.get_status_display(),
                f"{(Decimal(mins) / Decimal(60)).quantize(Decimal('0.1'))}",
            ]
        )

    if len(ticket_rows) > 1:
        flow.append(Paragraph("Tickets in period", h2))
        tt = Table(
            ticket_rows,
            colWidths=[16 * mm, 78 * mm, 24 * mm, 28 * mm, 18 * mm],
        )
        tt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _BRAND_NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ]
            )
        )
        flow.append(tt)

    flow.append(Spacer(1, 10 * mm))
    flow.append(
        Paragraph(
            "Generated by Luma Tech Solutions · lumatechsolutions.co.uk",
            ParagraphStyle("footer", parent=body, fontSize=8, textColor=colors.grey),
        )
    )

    doc.build(flow)
    return buf.getvalue()
