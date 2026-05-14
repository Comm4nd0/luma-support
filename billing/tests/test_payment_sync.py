from datetime import datetime, timezone as dt_tz
from decimal import Decimal
from unittest.mock import patch

import pytest

from billing.models import Invoice, Payment
from billing.tasks import sync_xero_payments


@pytest.mark.django_db
def test_sync_no_connection_returns_early():
    result = sync_xero_payments()
    assert result == "no-connection"


@pytest.mark.django_db
def test_sync_marks_invoice_paid(xero_connection, invoice):
    invoice.xero_invoice_id = "XERO-INV-1"
    invoice.save(update_fields=["xero_invoice_id"])

    fake_payment = {
        "PaymentID": "PAY-1",
        "Amount": "100.00",
        "Date": "/Date(1700000000000+0000)/",
        "Reference": "Bank ref 99",
        "Invoice": {"InvoiceID": "XERO-INV-1", "Status": "PAID"},
    }
    with patch(
        "billing.xero.client.XeroClient.list_payments",
        return_value=[fake_payment],
    ), patch("billing.xero.client.XeroClient._ensure_fresh_token", return_value=None):
        result = sync_xero_payments()

    assert "sync_xero_payments: 1" == result
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    assert invoice.paid_at is not None
    p = Payment.objects.get(xero_payment_id="PAY-1")
    assert p.amount == Decimal("100.00")
    assert p.reference == "Bank ref 99"


@pytest.mark.django_db
def test_sync_is_idempotent_on_payment_id(xero_connection, invoice):
    invoice.xero_invoice_id = "XERO-INV-1"
    invoice.save(update_fields=["xero_invoice_id"])
    fake_payment = {
        "PaymentID": "PAY-1",
        "Amount": "100.00",
        "Date": "/Date(1700000000000+0000)/",
        "Invoice": {"InvoiceID": "XERO-INV-1", "Status": "PAID"},
    }
    with patch(
        "billing.xero.client.XeroClient.list_payments",
        return_value=[fake_payment],
    ), patch("billing.xero.client.XeroClient._ensure_fresh_token", return_value=None):
        sync_xero_payments()
        sync_xero_payments()
    assert Payment.objects.filter(xero_payment_id="PAY-1").count() == 1


@pytest.mark.django_db
def test_sync_ignores_payments_for_unknown_invoices(xero_connection):
    fake = {
        "PaymentID": "PAY-X",
        "Amount": "10.00",
        "Date": "/Date(1700000000000+0000)/",
        "Invoice": {"InvoiceID": "UNKNOWN", "Status": "PAID"},
    }
    with patch(
        "billing.xero.client.XeroClient.list_payments",
        return_value=[fake],
    ), patch("billing.xero.client.XeroClient._ensure_fresh_token", return_value=None):
        result = sync_xero_payments()
    assert "0" in result
    assert not Payment.objects.exists()
