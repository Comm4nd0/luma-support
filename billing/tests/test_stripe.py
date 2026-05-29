"""Stripe payment-link task and webhook handler."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client as DjangoClient
from django.urls import reverse

from billing import stripe_client
from billing.models import Invoice, Payment
from billing.tasks import create_stripe_payment_link, push_invoice_to_xero

# ----- task -------------------------------------------------------------


@pytest.mark.django_db
def test_create_stripe_payment_link_no_op_when_unconfigured(invoice, settings):
    settings.STRIPE_API_KEY = ""
    result = create_stripe_payment_link(invoice.pk)
    assert result == "stripe-disabled"
    invoice.refresh_from_db()
    assert invoice.stripe_payment_link_url == ""


@pytest.mark.django_db
def test_create_stripe_payment_link_no_op_when_already_linked(invoice, settings):
    settings.STRIPE_API_KEY = "sk_test"
    invoice.stripe_payment_link_url = "https://buy.stripe.com/existing"
    invoice.save(update_fields=["stripe_payment_link_url"])
    with patch.object(stripe_client, "create_payment_link") as mock:
        result = create_stripe_payment_link(invoice.pk)
    mock.assert_not_called()
    assert result == "already-linked"


@pytest.mark.django_db
def test_create_stripe_payment_link_persists_url(invoice, settings):
    settings.STRIPE_API_KEY = "sk_test"
    with patch.object(
        stripe_client, "create_payment_link", return_value="https://buy.stripe.com/abc"
    ):
        result = create_stripe_payment_link(invoice.pk)
    assert result == "linked:https://buy.stripe.com/abc"
    invoice.refresh_from_db()
    assert invoice.stripe_payment_link_url == "https://buy.stripe.com/abc"


@pytest.mark.django_db
def test_create_stripe_payment_link_missing_invoice(settings):
    settings.STRIPE_API_KEY = "sk_test"
    result = create_stripe_payment_link(999_999)
    assert result == "missing"


@pytest.mark.django_db
def test_create_stripe_payment_link_skipped_for_zero_total(client_record, settings):
    settings.STRIPE_API_KEY = "sk_test"
    inv = Invoice.objects.create(client=client_record, kind=Invoice.Kind.ONE_OFF)
    # total defaults to 0 — create_payment_link returns None.
    result = create_stripe_payment_link(inv.pk)
    assert result == "skipped"


# ----- push_invoice_to_xero wiring --------------------------------------


@pytest.mark.django_db
def test_push_to_xero_triggers_stripe_link(invoice, xero_connection):
    """Pushing to Xero as AUTHORISED queues the Stripe link task."""
    with patch("billing.tasks.create_stripe_payment_link") as link_task, patch(
        "billing.xero.client.XeroClient"
    ) as XeroCls:
        XeroCls.return_value.create_invoice.side_effect = (
            lambda inv, status: setattr(inv, "xero_invoice_id", "xero-123")
            or inv.save(update_fields=["xero_invoice_id"])
        )
        push_invoice_to_xero(invoice.pk, "AUTHORISED")
    link_task.delay.assert_called_once_with(invoice.pk)


# ----- create_payment_link wrapper --------------------------------------


@pytest.mark.django_db
def test_create_payment_link_skips_zero_total(client_record, settings):
    settings.STRIPE_API_KEY = "sk_test"
    inv = Invoice.objects.create(client=client_record, kind=Invoice.Kind.ONE_OFF)
    assert stripe_client.create_payment_link(inv) is None


@pytest.mark.django_db
def test_create_payment_link_calls_stripe_sdk(invoice, settings):
    """The wrapper passes the right shape into stripe.Price + PaymentLink."""
    settings.STRIPE_API_KEY = "sk_test"
    import stripe

    fake_price = type("P", (), {"id": "price_abc"})()
    fake_link = type("L", (), {"url": "https://buy.stripe.com/abc"})()

    with patch.object(stripe.Price, "create", return_value=fake_price) as price_create, \
         patch.object(stripe.PaymentLink, "create", return_value=fake_link) as link_create:
        url = stripe_client.create_payment_link(invoice)

    assert url == "https://buy.stripe.com/abc"
    args, kwargs = price_create.call_args
    assert kwargs["unit_amount"] == int(invoice.total * 100)
    assert kwargs["currency"] == "gbp"
    assert kwargs["metadata"]["invoice_id"] == str(invoice.pk)
    args, kwargs = link_create.call_args
    assert kwargs["line_items"][0]["price"] == "price_abc"


# ----- webhook ----------------------------------------------------------


@pytest.fixture
def webhook_url():
    return reverse("v1:stripe-webhook")


def _fake_event(event_type, data_object):
    return {"type": event_type, "data": {"object": data_object}}


@pytest.mark.django_db
def test_webhook_invalid_signature_returns_400(webhook_url, settings):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    client = DjangoClient()
    with patch(
        "billing.webhooks.verify_webhook", side_effect=ValueError("bad sig")
    ):
        resp = client.post(
            webhook_url, data=b"{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=bad",
        )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_webhook_no_secret_configured_returns_400(webhook_url, settings):
    settings.STRIPE_WEBHOOK_SECRET = ""
    client = DjangoClient()
    resp = client.post(
        webhook_url, data=b"{}", content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=anything",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_webhook_checkout_completed_records_payment(invoice, webhook_url, settings):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    event = _fake_event(
        "checkout.session.completed",
        {
            "id": "cs_test_123",
            "metadata": {"invoice_id": str(invoice.pk)},
            "payment_intent": "pi_test_abc",
            "amount_total": 10000,  # £100.00 in pence
        },
    )
    client = DjangoClient()
    with patch("billing.webhooks.verify_webhook", return_value=event):
        resp = client.post(
            webhook_url, data=b"{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=ok",
        )

    assert resp.status_code == 200
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    assert invoice.paid_at is not None
    p = Payment.objects.get()
    assert p.stripe_payment_intent_id == "pi_test_abc"
    assert p.amount == Decimal("100.00")
    assert p.invoice == invoice


@pytest.mark.django_db
def test_webhook_is_idempotent_on_replay(invoice, webhook_url, settings):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    event = _fake_event(
        "checkout.session.completed",
        {
            "id": "cs_test_123",
            "metadata": {"invoice_id": str(invoice.pk)},
            "payment_intent": "pi_test_abc",
            "amount_total": 10000,
        },
    )
    client = DjangoClient()
    with patch("billing.webhooks.verify_webhook", return_value=event):
        client.post(
            webhook_url, data=b"{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=ok",
        )
        client.post(
            webhook_url, data=b"{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=ok",
        )
    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_webhook_unknown_invoice_id_does_not_error(webhook_url, settings):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    event = _fake_event(
        "checkout.session.completed",
        {
            "id": "cs_test",
            "metadata": {"invoice_id": "99999"},
            "payment_intent": "pi_test",
            "amount_total": 5000,
        },
    )
    client = DjangoClient()
    with patch("billing.webhooks.verify_webhook", return_value=event):
        resp = client.post(
            webhook_url, data=b"{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=ok",
        )
    assert resp.status_code == 200
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_webhook_payment_intent_succeeded_backup_path(invoice, webhook_url, settings):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    event = _fake_event(
        "payment_intent.succeeded",
        {
            "id": "pi_test_zzz",
            "metadata": {"invoice_id": str(invoice.pk)},
            "amount": 2500,
        },
    )
    client = DjangoClient()
    with patch("billing.webhooks.verify_webhook", return_value=event):
        resp = client.post(
            webhook_url, data=b"{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=ok",
        )
    assert resp.status_code == 200
    p = Payment.objects.get()
    assert p.stripe_payment_intent_id == "pi_test_zzz"
    assert p.amount == Decimal("25.00")
