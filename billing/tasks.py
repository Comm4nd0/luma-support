"""Celery tasks: contract invoice rollup, push to Xero, payment sync."""
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

from clients.models import CarePlanTier, Client


@shared_task
def chase_overdue_invoices():
    """Dunning sweep — runs daily.

    For each AUTHORISED/SENT invoice past `due_date`, fire reminders at
    3 / 7 / 14 days overdue. We email the client (if there's a recipient
    address) and create an in-app `INVOICE_OVERDUE` notification for
    Marco. Deduped per-invoice per-bucket via the audit log so the
    daily beat doesn't double-alert.
    """

    from django.conf import settings as _settings
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.core.mail import send_mail
    from django.utils import timezone

    from audit import log as audit_log
    from audit.models import AuditLog
    from notifications.models import Notification

    from .models import Invoice

    User = get_user_model()
    today = timezone.localdate()
    qs = Invoice.objects.filter(
        status__in=[Invoice.Status.SENT, Invoice.Status.AUTHORISED],
        due_date__lt=today,
    ).select_related("client")

    inv_ct = ContentType.objects.get_for_model(Invoice)
    sent = 0
    for invoice in qs:
        days_overdue = (today - invoice.due_date).days
        bucket = _dunning_bucket(days_overdue)
        if bucket is None:
            continue

        already = AuditLog.objects.filter(
            action="invoice.dunning",
            target_ct=inv_ct,
            target_id=invoice.pk,
            metadata__bucket=bucket,
        ).exists()
        if already:
            continue

        recipient = invoice.client.email
        if recipient:
            subject = (
                f"Invoice #{invoice.pk} — {bucket} days overdue"
                if bucket != "1"
                else f"Invoice #{invoice.pk} reminder"
            )
            body = (
                f"Hi {invoice.client.name},\n\n"
                f"This is a friendly reminder that invoice #{invoice.pk} "
                f"({invoice.currency} {invoice.total}) was due "
                f"{invoice.due_date:%Y-%m-%d} and is now {days_overdue} "
                f"day{'s' if days_overdue != 1 else ''} overdue.\n\n"
            )
            if invoice.stripe_payment_link_url:
                body += f"Pay online: {invoice.stripe_payment_link_url}\n\n"
            body += "Thanks,\nLuma Tech Solutions\n"
            send_mail(
                subject,
                body,
                _settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )

        title = (
            f"Invoice #{invoice.pk} {days_overdue}d overdue — "
            f"{invoice.client.name}"
        )
        body = (
            f"{invoice.currency} {invoice.total} due "
            f"{invoice.due_date:%Y-%m-%d}."
        )
        for u in User.objects.filter(
            role__in=["admin", "engineer"], is_active=True
        ):
            Notification.objects.create(
                user=u,
                type=Notification.Type.INVOICE_OVERDUE,
                title=title,
                body=body,
            )
        audit_log(
            "invoice.dunning",
            target=invoice,
            bucket=bucket,
            days_overdue=days_overdue,
            emailed=bool(recipient),
        )
        sent += 1

    return f"chase_overdue_invoices: {sent} reminders sent"


def _dunning_bucket(days_overdue: int) -> str | None:
    """Map "days overdue" to a reminder bucket. 3/7/14 buckets, then weekly."""
    if days_overdue in (3, 7, 14):
        return str(days_overdue)
    if days_overdue >= 21 and days_overdue % 7 == 0:
        return f"{days_overdue}"
    return None


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
    """Push a draft invoice to Xero. Idempotent if it already has xero_invoice_id.

    Once on Xero as AUTHORISED, the matching Stripe Payment Link is
    enqueued so clients can pay online from the invoice email.
    """
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
        raise self.retry(exc=exc) from exc

    if status == "AUTHORISED":
        create_stripe_payment_link.delay(invoice.pk)
    return f"pushed:{invoice.xero_invoice_id}"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def create_stripe_payment_link(self, invoice_id: int):
    """Create a Stripe Payment Link for `invoice_id` and persist the URL.

    No-op when STRIPE_API_KEY is empty or the invoice already has a link.
    """
    from . import stripe_client
    from .models import Invoice

    if not stripe_client.is_configured():
        return "stripe-disabled"

    try:
        invoice = Invoice.objects.select_related("client").get(pk=invoice_id)
    except Invoice.DoesNotExist:
        return "missing"
    if invoice.stripe_payment_link_url:
        return "already-linked"

    try:
        url = stripe_client.create_payment_link(invoice)
    except Exception as exc:
        raise self.retry(exc=exc) from exc
    if not url:
        return "skipped"

    invoice.stripe_payment_link_url = url
    invoice.save(update_fields=["stripe_payment_link_url", "updated_at"])
    return f"linked:{url}"


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
        raise self.retry(exc=exc) from exc

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
