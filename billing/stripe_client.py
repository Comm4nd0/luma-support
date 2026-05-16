"""Thin wrapper around the stripe SDK.

Kept narrow so tests can patch a handful of named functions instead of
the whole `stripe` namespace, and so the rest of the app doesn't depend
on the SDK directly.
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings


def is_configured() -> bool:
    return bool(getattr(settings, "STRIPE_API_KEY", ""))


def _configure() -> None:
    import stripe

    stripe.api_key = settings.STRIPE_API_KEY


def create_payment_link(invoice) -> Optional[str]:
    """Create (or re-use) a Stripe Payment Link for `invoice`.

    Returns the link URL, or None when Stripe isn't configured or the
    invoice has no positive total. Idempotency is enforced at the
    Invoice level by the caller (see `billing.tasks.create_stripe_payment_link`).
    """
    if not is_configured():
        return None

    amount_minor = int((invoice.total or 0) * 100)
    if amount_minor <= 0:
        return None

    _configure()
    import stripe

    currency = (invoice.currency or "GBP").lower()
    metadata = {"invoice_id": str(invoice.pk)}

    price = stripe.Price.create(
        unit_amount=amount_minor,
        currency=currency,
        product_data={
            "name": f"Invoice #{invoice.pk} — {invoice.client.name}",
        },
        metadata=metadata,
    )
    link = stripe.PaymentLink.create(
        line_items=[{"price": price.id, "quantity": 1}],
        metadata=metadata,
    )
    return link.url


def verify_webhook(payload: bytes, sig_header: str):
    """Validate Stripe webhook signature and return the parsed event.

    Raises ValueError on missing config or invalid signature so the
    caller can return a 400.
    """
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or ""
    if not secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET not configured")

    import stripe

    return stripe.Webhook.construct_event(payload, sig_header, secret)
