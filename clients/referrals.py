"""Referral credit flow.

Triggered when a `leads.Lead` with `referring_client` set is converted
to a Client (i.e. WON). Adds the configured credit to the referrer's
`clients.ReferralCode` balance, notifies Marco plus the referring
client's user (if any), and writes an audit-log row.

`apply_credit_to_invoice` is called by the contract-invoice generator
to drain available credit as a negative `InvoiceLine`.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from audit import log as audit_log

from .models import ReferralCode


def _credit_amount() -> Decimal:
    raw = getattr(settings, "REFERRAL_CREDIT_GBP", Decimal("25.00"))
    return Decimal(str(raw))


@transaction.atomic
def credit_referrer(lead) -> ReferralCode | None:
    """Add a referral credit to the lead's `referring_client`, if any.

    Idempotent per-lead: writes a no-credit audit row if the lead was
    already credited (tracked via the audit log).
    """
    if not lead.referring_client_id:
        return None
    code = ReferralCode.for_client(lead.referring_client)

    # Idempotency: the audit log is the source of truth for "have we
    # already credited this lead?".
    from django.contrib.contenttypes.models import ContentType

    from audit.models import AuditLog

    lead_ct = ContentType.objects.get_for_model(lead.__class__)
    already = AuditLog.objects.filter(
        action="referral.credit",
        target_ct=lead_ct,
        target_id=lead.pk,
    ).exists()
    if already:
        return code

    amount = _credit_amount()
    code.credit_balance = (code.credit_balance or Decimal("0")) + amount
    code.lifetime_credit = (code.lifetime_credit or Decimal("0")) + amount
    code.save(
        update_fields=["credit_balance", "lifetime_credit", "updated_at"]
    )

    audit_log(
        "referral.credit",
        target=lead,
        amount=str(amount),
        referrer_client_id=lead.referring_client_id,
        new_balance=str(code.credit_balance),
    )

    _notify(lead, amount)
    return code


def _notify(lead, amount: Decimal) -> None:
    """Send in-app notifications to staff + the referring client's user(s)."""
    try:
        from notifications.models import Notification
        from notifications.tasks import send_push
    except Exception:
        return

    User = get_user_model()
    targets: set[int] = set()

    # Every staff member (Marco's hat).
    for u in User.objects.filter(
        role__in=["admin", "engineer"], is_active=True
    ).values_list("pk", flat=True):
        targets.add(u)

    # The referring client's user(s), if they have a portal account.
    for u in User.objects.filter(
        client_id=lead.referring_client_id, is_active=True
    ).values_list("pk", flat=True):
        targets.add(u)

    title = f"Referral credit £{amount}: {lead.name}"
    body = (
        f"{lead.referring_client.name} referred {lead.name} — credit "
        f"£{amount} added to their account."
    )
    for uid in targets:
        notif = Notification.objects.create(
            user_id=uid,
            type=Notification.Type.REFERRAL_CREDIT,
            title=title,
            body=body,
        )
        try:
            send_push.delay(notif.pk)
        except Exception:
            pass


def apply_credit_to_invoice(invoice) -> Decimal:
    """Drain available referral credit onto a draft invoice as a negative line.

    Caps the credit at the invoice subtotal so an invoice never goes
    negative. Returns the amount applied (Decimal('0') if no credit).
    """
    from billing.models import InvoiceLine

    code = getattr(invoice.client, "referral_code", None)
    if code is None or code.credit_balance <= 0:
        return Decimal("0")

    available = code.credit_balance
    cap = invoice.subtotal or Decimal("0")
    apply = min(available, cap)
    if apply <= 0:
        return Decimal("0")

    InvoiceLine.objects.create(
        invoice=invoice,
        description="Referral credit",
        quantity=Decimal("1"),
        unit_amount=-apply,
        account_code=getattr(settings, "DEFAULT_ACCOUNT_CODE", ""),
        tax_type=getattr(settings, "DEFAULT_TAX_TYPE", ""),
    )
    code.credit_balance = available - apply
    code.save(update_fields=["credit_balance", "updated_at"])
    audit_log(
        "referral.apply",
        target=invoice,
        amount=str(apply),
        remaining_balance=str(code.credit_balance),
    )
    return apply
