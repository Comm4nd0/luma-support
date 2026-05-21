"""UK VAT roll-up — quarterly box totals for Making Tax Digital export.

Source of truth is the local Invoice row (subtotal / tax / total), which
mirrors what was pushed to Xero. The aggregation is a single SQL query
across invoices closed (paid / authorised) within the requested period.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import Invoice


@dataclass
class VatSummary:
    period_start: date
    period_end: date
    sales_ex_vat: Decimal  # Box 6 — total value of sales excluding VAT
    vat_on_sales: Decimal  # Box 1 — VAT due on sales
    invoice_count: int

    @property
    def total_inc_vat(self) -> Decimal:
        return self.sales_ex_vat + self.vat_on_sales


_QUARTER_BOUNDS = {
    1: ((1, 1), (3, 31)),
    2: ((4, 1), (6, 30)),
    3: ((7, 1), (9, 30)),
    4: ((10, 1), (12, 31)),
}


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    """Return (first_day, last_day_inclusive) for a calendar quarter."""
    if quarter not in _QUARTER_BOUNDS:
        raise ValueError("quarter must be 1..4")
    (sm, sd), (em, ed) = _QUARTER_BOUNDS[quarter]
    return date(year, sm, sd), date(year, em, ed)


def vat_summary(year: int, quarter: int) -> VatSummary:
    """Aggregate AUTHORISED/PAID invoices in the period into a VatSummary.

    "Closed" = status in {AUTHORISED, PAID} — Xero treats those as
    accounted-for. DRAFT and VOIDED are excluded.
    """
    start, end = quarter_bounds(year, quarter)
    qs = Invoice.objects.filter(
        status__in=[Invoice.Status.AUTHORISED, Invoice.Status.PAID],
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    agg = qs.aggregate(
        sales=Sum("subtotal"),
        vat=Sum("tax"),
    )
    return VatSummary(
        period_start=start,
        period_end=end,
        sales_ex_vat=Decimal(agg["sales"] or 0),
        vat_on_sales=Decimal(agg["vat"] or 0),
        invoice_count=qs.count(),
    )
