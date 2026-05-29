"""Per-client profitability rollup."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client as DjangoClient

from billing.models import Invoice
from billing.profitability import client_profitability
from tickets.models import Ticket, TimeEntry

pytestmark = pytest.mark.django_db


def test_revenue_includes_authorised_invoices_and_monthly_fee(
    client_record, settings
):
    settings.PROFITABILITY_HOURLY_COST_GBP = "35"
    client_record.monthly_fee = Decimal("100")
    client_record.save()
    Invoice.objects.create(
        client=client_record, kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.AUTHORISED,
        subtotal=Decimal("200"), total=Decimal("200"),
    )
    rows = client_profitability(date.today() - timedelta(days=30), date.today())
    by_id = {r.client_id: r for r in rows}
    r = by_id[client_record.pk]
    # Revenue = 200 invoice + ~1 month of £100 fee = ~300 (allow small slop
    # on the days-to-months pro-rate).
    assert Decimal("295") <= r.revenue <= Decimal("310")


def test_cost_is_hours_times_rate(engineer_user, client_record, settings):
    settings.PROFITABILITY_HOURLY_COST_GBP = "40"
    t = Ticket.objects.create(client=client_record, subject="x")
    TimeEntry.objects.create(ticket=t, user=engineer_user, minutes=90)
    rows = client_profitability(date.today() - timedelta(days=30), date.today())
    r = next(r for r in rows if r.client_id == client_record.pk)
    assert r.hours_logged == Decimal("1.50")
    assert r.estimated_cost == Decimal("60.00")


def test_margin_pct_handles_zero_revenue(client_record, settings):
    settings.PROFITABILITY_HOURLY_COST_GBP = "35"
    rows = client_profitability(date.today() - timedelta(days=30), date.today())
    r = next(r for r in rows if r.client_id == client_record.pk)
    assert r.revenue == Decimal("0.00")
    assert r.margin_pct is None


def test_portal_page_and_csv_export(admin_user, client_record):
    Invoice.objects.create(
        client=client_record, kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.PAID,
        subtotal=Decimal("100"), total=Decimal("100"),
    )
    web = DjangoClient()
    web.force_login(admin_user)
    page = web.get("/billing/reports/profitability/")
    assert page.status_code == 200
    csv_resp = web.get("/billing/reports/profitability/?export=csv")
    assert csv_resp.status_code == 200
    assert csv_resp["Content-Type"] == "text/csv"
    assert b"margin" in csv_resp.content
