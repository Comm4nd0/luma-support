"""Celery tasks: contract invoice rollup and Xero payment sync."""
from celery import shared_task
from django.utils import timezone

from clients.models import CarePlanTier, Client


@shared_task
def generate_contract_invoices():
    """Run on the 1st of each month — create draft contract invoices."""
    from .services import generate_contract_invoice

    today = timezone.localdate()
    created = 0
    qs = (
        Client.objects.exclude(care_plan_tier=CarePlanTier.NONE)
        .exclude(monthly_fee__isnull=True)
        .filter(monthly_fee__gt=0)
    )
    for client in qs:
        _, was_new = generate_contract_invoice(client, today)
        if was_new:
            created += 1
    return f"generate_contract_invoices: {created} created"
