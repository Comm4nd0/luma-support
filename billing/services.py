"""Pure-Python invoice generation services.

These run synchronously (callable from views or tasks). The Celery tasks
in ``billing.tasks`` are thin wrappers that schedule them.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from itertools import groupby

from django.conf import settings
from django.db import transaction

from clients.models import CarePlanTier, Client
from tickets.models import TimeEntry

from .models import Invoice, InvoiceLine


def _first_of_month(today: date) -> date:
    return today.replace(day=1)


def _last_day_of_month(first: date) -> date:
    if first.month == 12:
        next_first = first.replace(year=first.year + 1, month=1)
    else:
        next_first = first.replace(month=first.month + 1)
    return next_first - timedelta(days=1)


def generate_contract_invoice(
    client: Client, today: date
) -> tuple[Invoice | None, bool]:
    """Create this month's contract invoice for `client` if it doesn't exist.

    Returns ``(invoice, created)``. ``invoice`` is ``None`` when the client
    isn't eligible (no tier, or no monthly_fee).
    """
    if client.care_plan_tier == CarePlanTier.NONE:
        return None, False
    if not client.monthly_fee or client.monthly_fee <= 0:
        return None, False

    period_start = _first_of_month(today)
    period_end = _last_day_of_month(period_start)

    invoice, was_new = Invoice.objects.get_or_create(
        client=client,
        kind=Invoice.Kind.CONTRACT,
        period_start=period_start,
        defaults={
            "period_end": period_end,
            "currency": settings.DEFAULT_CURRENCY,
            "status": Invoice.Status.DRAFT,
            "due_date": period_start + timedelta(days=14),
        },
    )
    if not was_new:
        return invoice, False

    InvoiceLine.objects.create(
        invoice=invoice,
        description=(
            f"{client.get_care_plan_tier_display()} support — "
            f"{period_start:%B %Y}"
        ),
        quantity=Decimal("1.00"),
        unit_amount=client.monthly_fee,
        account_code=settings.DEFAULT_ACCOUNT_CODE,
        tax_type=settings.DEFAULT_TAX_TYPE,
    )
    invoice.recalculate_totals()
    invoice.save(update_fields=["subtotal", "tax", "total", "updated_at"])

    # Apply any outstanding referral credit as a negative line. Pulled in
    # lazily so this module doesn't import `clients.referrals` at startup.
    try:
        from clients.referrals import apply_credit_to_invoice

        if apply_credit_to_invoice(invoice) > 0:
            invoice.recalculate_totals()
            invoice.save(
                update_fields=["subtotal", "tax", "total", "updated_at"]
            )
    except Exception:
        pass

    return invoice, True


@transaction.atomic
def generate_time_invoice(client: Client) -> Invoice | None:
    """Bundle unbilled billable time for `client` into a new draft invoice."""
    qs = list(
        TimeEntry.objects.filter(
            ticket__client=client, billable=True, invoice_line__isnull=True
        )
        .select_related("ticket")
        .order_by("ticket_id", "created_at")
    )
    if not qs:
        return None

    rate = client.effective_hourly_rate()
    invoice = Invoice.objects.create(
        client=client,
        kind=Invoice.Kind.TIME,
        currency=settings.DEFAULT_CURRENCY,
        status=Invoice.Status.DRAFT,
    )

    for _ticket_id, group in groupby(qs, key=lambda e: e.ticket_id):
        entries = list(group)
        ticket = entries[0].ticket
        total_minutes = sum(e.minutes for e in entries)
        hours = (Decimal(total_minutes) / Decimal(60)).quantize(Decimal("0.01"))
        line = InvoiceLine.objects.create(
            invoice=invoice,
            description=f"#{ticket.pk} {ticket.subject}",
            quantity=hours,
            unit_amount=rate,
            account_code=settings.DEFAULT_ACCOUNT_CODE,
            tax_type=settings.DEFAULT_TAX_TYPE,
        )
        TimeEntry.objects.filter(pk__in=[e.pk for e in entries]).update(
            invoice_line=line
        )

    invoice.recalculate_totals()
    invoice.save(update_fields=["subtotal", "tax", "total", "updated_at"])
    return invoice
