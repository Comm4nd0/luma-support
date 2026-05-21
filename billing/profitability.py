"""Per-client profitability rollup over an arbitrary window.

Revenue = sum of (subtotal) on AUTHORISED + PAID invoices created in
the window, plus a pro-rata slice of the client's monthly care-plan
fee for any portion of the window that overlapped the period.

Cost = total minutes logged (any TimeEntry, billable or not) × a flat
estimated hourly cost from settings (``PROFITABILITY_HOURLY_COST_GBP``,
default 35). This isn't payroll-accurate — it's a directional
"is this client paying enough?" metric. Per-user cost rates can layer
on later if Marco hires.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum

from clients.models import Client
from tickets.models import TimeEntry

from .models import Invoice


@dataclass
class ProfitabilityRow:
    client_id: int
    name: str
    revenue: Decimal
    hours_logged: Decimal
    estimated_cost: Decimal

    @property
    def margin(self) -> Decimal:
        return (self.revenue - self.estimated_cost).quantize(Decimal("0.01"))

    @property
    def margin_pct(self) -> int | None:
        if not self.revenue:
            return None
        return int(round(100 * float(self.margin) / float(self.revenue)))


def _months_overlap(start: date, end: date) -> Decimal:
    """Approximate number of months a [start, end] window spans —
    enough for the monthly-fee pro-rate, which doesn't need second
    precision."""
    days = (end - start).days + 1
    return (Decimal(days) / Decimal(30)).quantize(Decimal("0.01"))


def client_profitability(start: date, end: date) -> list[ProfitabilityRow]:
    cost_per_hour = Decimal(
        str(getattr(settings, "PROFITABILITY_HOURLY_COST_GBP", "35"))
    )
    months = _months_overlap(start, end)
    rows: list[ProfitabilityRow] = []
    for client in Client.objects.all():
        invoiced = (
            Invoice.objects.filter(
                client=client,
                status__in=[Invoice.Status.AUTHORISED, Invoice.Status.PAID],
                created_at__date__gte=start,
                created_at__date__lte=end,
            ).aggregate(total=Sum("subtotal"))["total"]
            or Decimal("0")
        )
        monthly_fee = client.monthly_fee or Decimal("0")
        revenue = (Decimal(invoiced) + monthly_fee * months).quantize(Decimal("0.01"))

        minutes = (
            TimeEntry.objects.filter(
                ticket__client=client,
                created_at__date__gte=start,
                created_at__date__lte=end,
            ).aggregate(total=Sum("minutes"))["total"]
            or 0
        )
        hours = (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.01"))
        cost = (hours * cost_per_hour).quantize(Decimal("0.01"))
        rows.append(
            ProfitabilityRow(
                client_id=client.pk, name=client.name,
                revenue=revenue, hours_logged=hours, estimated_cost=cost,
            )
        )
    # Worst margin first so the unprofitable accounts are top of the
    # report — that's the one Marco needs to act on.
    rows.sort(key=lambda r: r.margin)
    return rows
