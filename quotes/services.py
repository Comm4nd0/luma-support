"""Quote workflow helpers — send, accept, convert.

Kept separate from `models.py` so the model file stays focused on
fields and the workflow's side-effects (audit, lead activity, invoice
creation, email) live next to each other.
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from audit import log as audit_log
from billing.models import Invoice, InvoiceLine

from .models import Quote, QuoteStatus


def send_quote(quote: Quote, *, by_user=None) -> bool:
    """Email the accept link to the prospect and stamp `sent_at`.

    Returns True if an email was actually sent (recipient resolved),
    False otherwise — the quote still transitions to SENT either way
    so Marco's pipeline reflects intent.
    """
    if quote.status == QuoteStatus.DRAFT:
        quote.status = QuoteStatus.SENT
        quote.sent_at = timezone.now()
        quote.save(update_fields=["status", "sent_at", "updated_at"])

    recipient = quote.recipient_email
    sent = False
    if recipient:
        link = (
            f"{settings.SITE_URL.rstrip('/')}/q/{quote.accept_token}/"
        )
        subject = f"Quote {quote.number} from Luma Tech Solutions"
        body = (
            f"Hi {quote.recipient_name or 'there'},\n\n"
            f"Here's your quote — {quote.number}, valid until "
            f"{quote.valid_until:%Y-%m-%d}.\n\n"
            f"Total: {quote.currency} {quote.total}\n\n"
            f"View and accept it here:\n{link}\n\n"
            f"Any questions, just reply to this email.\n\n"
            f"Luma Tech Solutions\n"
        )
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        sent = True

    audit_log("quote.send", actor=by_user, target=quote, sent=sent)
    _log_lead_activity(quote, by_user, kind_quote_sent=True, sent=sent)
    return sent


@transaction.atomic
def accept_quote(
    quote: Quote,
    *,
    accepted_by_name: str = "",
    accepted_ip: str = "",
) -> Invoice:
    """Mark a quote ACCEPTED and create a matching DRAFT Invoice.

    Idempotent — calling twice returns the same invoice. The linked
    Lead (if any) is converted to a Client and transitioned to WON.
    """
    if quote.converted_invoice_id is not None:
        return quote.converted_invoice

    client = _resolve_or_create_client(quote)

    invoice = Invoice.objects.create(
        client=client,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.DRAFT,
        subtotal=quote.subtotal,
        tax=quote.tax,
        total=quote.total,
        currency=quote.currency,
        notes=(
            f"Created from accepted quote {quote.number}."
            + (f"\n\n{quote.notes}" if quote.notes else "")
        ),
        created_by=quote.created_by,
    )
    for line in quote.lines.all().order_by("pk"):
        InvoiceLine.objects.create(
            invoice=invoice,
            description=line.description,
            quantity=line.quantity,
            unit_amount=line.unit_amount,
            account_code=line.account_code,
            tax_type=line.tax_type,
        )
    invoice.recalculate_totals()
    invoice.save(update_fields=["subtotal", "total"])

    quote.status = QuoteStatus.ACCEPTED
    quote.accepted_at = timezone.now()
    quote.accepted_by_name = accepted_by_name[:200]
    quote.accepted_ip = accepted_ip[:64]
    quote.client = client
    quote.converted_invoice = invoice
    quote.save(
        update_fields=[
            "status",
            "accepted_at",
            "accepted_by_name",
            "accepted_ip",
            "client",
            "converted_invoice",
            "updated_at",
        ]
    )
    audit_log("quote.accept", target=quote, invoice_id=invoice.pk)
    _log_lead_activity(quote, None, kind_accept=True)
    return invoice


def reject_quote(quote: Quote, *, reason: str = "", by_user=None) -> None:
    quote.status = QuoteStatus.REJECTED
    quote.rejected_at = timezone.now()
    quote.rejection_reason = reason[:200]
    quote.save(
        update_fields=[
            "status",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    audit_log("quote.reject", actor=by_user, target=quote, reason=reason)


def _resolve_or_create_client(quote: Quote):
    """Return the Client the invoice should be raised against."""
    if quote.client_id:
        return quote.client
    if quote.lead_id:
        # convert_to_client is idempotent — re-uses an existing client
        # if the lead has already been converted.
        return quote.lead.convert_to_client()
    raise ValueError(
        "Quote has neither a client nor a lead — nowhere to invoice."
    )


def _log_lead_activity(
    quote: Quote,
    actor,
    *,
    kind_quote_sent: bool = False,
    kind_accept: bool = False,
    sent: bool = False,
) -> None:
    """Mirror quote events onto the linked lead's timeline."""
    if quote.lead_id is None:
        return
    try:
        from leads.models import ActivityKind, LeadActivity
    except Exception:
        return
    if kind_quote_sent:
        body = (
            f"Quote {quote.number} sent" if sent else f"Quote {quote.number} marked sent (no email)"
        )
        LeadActivity.objects.create(
            lead_id=quote.lead_id,
            kind=ActivityKind.QUOTE_SENT,
            body=body,
            actor=actor,
        )
    elif kind_accept:
        LeadActivity.objects.create(
            lead_id=quote.lead_id,
            kind=ActivityKind.NOTE,
            body=f"Quote {quote.number} accepted",
            actor=actor,
        )
