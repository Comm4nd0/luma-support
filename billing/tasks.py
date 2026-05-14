"""Celery tasks: contract invoice rollup, push to Xero, payment sync."""
from datetime import timedelta
from decimal import Decimal

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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def push_invoice_to_xero(self, invoice_id: int, status: str = "AUTHORISED"):
    """Push a draft invoice to Xero. Idempotent if it already has xero_invoice_id."""
    from .models import Invoice, XeroConnection
    from .xero.client import XeroClient

    try:
        invoice = Invoice.objects.select_related("client").get(pk=invoice_id)
    except Invoice.DoesNotExist:
        return "missing"
    if invoice.xero_invoice_id:
        return "already-synced"
    try:
        conn = XeroConnection.objects.get(pk=1)
    except XeroConnection.DoesNotExist:
        return "no-connection"

    api = XeroClient(conn)
    try:
        api.create_invoice(invoice, status=status)
    except Exception as exc:  # network/auth failures only — let Celery retry.
        raise self.retry(exc=exc)
    return f"pushed:{invoice.xero_invoice_id}"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_xero_payments(self):
    """Pull recent Xero payments and reflect them onto our Invoice rows."""
    from .models import Invoice, Payment, XeroConnection
    from .xero.client import XeroClient, parse_xero_datetime

    try:
        conn = XeroConnection.objects.get(pk=1)
    except XeroConnection.DoesNotExist:
        return "no-connection"

    api = XeroClient(conn)
    since = timezone.now() - timedelta(hours=24)
    try:
        payments = api.list_payments(since=since)
    except Exception as exc:
        raise self.retry(exc=exc)

    updated = 0
    for raw in payments:
        xpid = raw.get("PaymentID")
        invoice_ref = raw.get("Invoice") or {}
        xinv = invoice_ref.get("InvoiceID")
        if not xpid or not xinv:
            continue
        try:
            invoice = Invoice.objects.get(xero_invoice_id=xinv)
        except Invoice.DoesNotExist:
            continue

        amount = Decimal(str(raw.get("Amount", "0")))
        paid_at = parse_xero_datetime(raw.get("Date") or raw.get("DateString") or "")
        Payment.objects.update_or_create(
            xero_payment_id=xpid,
            defaults={
                "invoice": invoice,
                "amount": amount,
                "paid_at": paid_at,
                "reference": raw.get("Reference", "") or "",
            },
        )
        if (
            invoice_ref.get("Status") == "PAID"
            and invoice.status != Invoice.Status.PAID
        ):
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = paid_at
            invoice.xero_status = "PAID"
            invoice.xero_synced_at = timezone.now()
            invoice.save(
                update_fields=[
                    "status",
                    "paid_at",
                    "xero_status",
                    "xero_synced_at",
                    "updated_at",
                ]
            )
        updated += 1
    return f"sync_xero_payments: {updated}"
