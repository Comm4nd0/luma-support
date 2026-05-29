"""Thin wrapper around the stripe SDK.

Kept narrow so tests can patch a handful of named functions instead of
the whole `stripe` namespace, and so the rest of the app doesn't depend
on the SDK directly.
"""
from __future__ import annotations

from django.conf import settings


def is_configured() -> bool:
    return bool(getattr(settings, "STRIPE_API_KEY", ""))


def _configure() -> None:
    import stripe

    stripe.api_key = settings.STRIPE_API_KEY


def create_payment_link(invoice) -> str | None:
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


def create_customer_portal_session(client, return_url: str) -> str | None:
    """Create (or re-use) a Stripe billing-portal session URL for ``client``.

    Lazily creates the Stripe Customer on first call, caching the id on
    ``Client.stripe_customer_id`` so subsequent sessions skip the round
    trip. Returns ``None`` when Stripe isn't configured so the calling
    view can hide the button.
    """
    if not is_configured():
        return None
    _configure()
    import stripe

    customer_id = client.stripe_customer_id or ""
    if not customer_id:
        cust = stripe.Customer.create(
            email=client.email or "",
            name=client.name,
            metadata={"luma_client_id": str(client.pk)},
        )
        customer_id = cust.id
        client.stripe_customer_id = customer_id
        client.save(update_fields=["stripe_customer_id"])

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


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
