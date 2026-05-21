"""Quarterly VAT roll-up."""
from decimal import Decimal

import pytest
from django.test import Client as DjangoClient

from .models import Invoice
from .vat import quarter_bounds, vat_summary

pytestmark = pytest.mark.django_db


def test_quarter_bounds_q1():
    s, e = quarter_bounds(2026, 1)
    assert (s.month, s.day) == (1, 1)
    assert (e.month, e.day) == (3, 31)


def test_quarter_bounds_q4():
    s, e = quarter_bounds(2026, 4)
    assert (s.month, e.day) == (10, 31)


def test_summary_sums_authorised_and_paid(client_record):
    Invoice.objects.create(
        client=client_record, kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.AUTHORISED,
        subtotal=Decimal("100"), tax=Decimal("20"), total=Decimal("120"),
    )
    Invoice.objects.create(
        client=client_record, kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.PAID,
        subtotal=Decimal("50"), tax=Decimal("10"), total=Decimal("60"),
    )
    # Should NOT be included:
    Invoice.objects.create(
        client=client_record, kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.DRAFT,
        subtotal=Decimal("999"), tax=Decimal("0"), total=Decimal("999"),
    )

    # Use whatever quarter the test runs in for "current".
    from datetime import date
    today = date.today()
    quarter = ((today.month - 1) // 3) + 1
    summary = vat_summary(today.year, quarter)
    assert summary.sales_ex_vat == Decimal("150")
    assert summary.vat_on_sales == Decimal("30")
    assert summary.invoice_count == 2


def test_report_page_renders(admin_user):
    web = DjangoClient()
    web.force_login(admin_user)
    resp = web.get("/billing/reports/vat/")
    assert resp.status_code == 200
    assert b"VAT report" in resp.content


def test_report_csv_export(admin_user):
    web = DjangoClient()
    web.force_login(admin_user)
    resp = web.get("/billing/reports/vat/?year=2026&quarter=1&export=csv")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert b"sales_ex_vat" in resp.content
