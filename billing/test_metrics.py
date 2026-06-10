"""Tests for `billing.metrics` and the revenue dashboard."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from clients.models import CarePlanTier, Client

from . import metrics
from .models import Invoice, InvoiceLine


def _months_ago(anchor: date, n: int) -> date:
    """First of the month `n` calendar months before `anchor`.

    Subtracting fixed day counts and snapping to day 1 can land two
    offsets in the same month (e.g. 1 June − 62d and − 92d are both
    March), so use real month arithmetic.
    """
    year, month = anchor.year, anchor.month - n
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


def _make_contract_invoice(client: Client, period_start: date, total: Decimal):
    inv = Invoice.objects.create(
        client=client,
        kind=Invoice.Kind.CONTRACT,
        status=Invoice.Status.PAID,
        period_start=period_start,
        period_end=period_start,
        subtotal=total,
        total=total,
    )
    InvoiceLine.objects.create(
        invoice=inv, description="Care plan", quantity=1, unit_amount=total
    )
    return inv


# -----------------------------------------------------------------
# Current MRR / ARR
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_current_mrr_sums_active_clients():
    Client.objects.create(
        name="A",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )
    Client.objects.create(
        name="B",
        care_plan_tier=CarePlanTier.PROFESSIONAL,
        monthly_fee=Decimal("70.00"),
    )
    # No tier — excluded.
    Client.objects.create(
        name="No-plan", monthly_fee=Decimal("999.00")
    )
    assert metrics.current_mrr() == Decimal("100.00")
    assert metrics.arr() == Decimal("1200.00")


@pytest.mark.django_db
def test_current_mrr_excludes_lapsed_plans():
    Client.objects.create(
        name="Active",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )
    Client.objects.create(
        name="Expired",
        care_plan_tier=CarePlanTier.PROFESSIONAL,
        monthly_fee=Decimal("70.00"),
        care_plan_renewal=date.today() - timedelta(days=1),
    )
    assert metrics.current_mrr() == Decimal("30.00")


# -----------------------------------------------------------------
# History bucketing
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_mrr_history_classifies_new_expansion_contraction_churn():
    today = date.today().replace(day=1)
    one_ago = (today - timedelta(days=2)).replace(day=1)

    c1 = Client.objects.create(
        name="Steady",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )
    c2 = Client.objects.create(
        name="Expander",
        care_plan_tier=CarePlanTier.PROFESSIONAL,
        monthly_fee=Decimal("70.00"),
    )
    c3 = Client.objects.create(
        name="Churned",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )

    # Last month: all 3 paying.
    _make_contract_invoice(c1, one_ago, Decimal("30"))
    _make_contract_invoice(c2, one_ago, Decimal("50"))
    _make_contract_invoice(c3, one_ago, Decimal("30"))

    # This month: c1 steady, c2 expanded, c3 churned, c_new is new.
    c4 = Client.objects.create(
        name="Brand new",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )
    _make_contract_invoice(c1, today, Decimal("30"))
    _make_contract_invoice(c2, today, Decimal("70"))
    _make_contract_invoice(c4, today, Decimal("30"))

    history = metrics.mrr_history(months=3)
    # Last bucket = this month.
    current = history[-1]
    assert current.mrr == Decimal("130.00")
    assert current.new_mrr == Decimal("30.00")  # c4
    assert current.expansion_mrr == Decimal("20.00")  # c2 50 -> 70
    assert current.churn_mrr == Decimal("30.00")  # c3 dropped
    assert c3.pk in current.churned_clients


@pytest.mark.django_db
def test_gross_churn_rate_returns_fraction():
    today = date.today().replace(day=1)
    # window_days=120 → a 5-bucket history anchored 4 months back, and the
    # rate divides by the first bucket's MRR — so pay from the window start
    # (4 months ago) through last month, then churn this month.
    months_back = [_months_ago(today, n) for n in (4, 3, 2, 1)]
    c = Client.objects.create(
        name="A",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("100"),
    )
    for m in months_back:
        _make_contract_invoice(c, m, Decimal("100"))
    # No invoice this month -> churn.
    rate = metrics.gross_churn_rate(window_days=120)
    assert rate > 0


# -----------------------------------------------------------------
# Portal + API
# -----------------------------------------------------------------


@pytest.fixture
def auth_admin(client, admin_user):
    admin_user.totp_enabled = True
    admin_user.set_totp_secret("JBSWY3DPEHPK3PXP")
    admin_user.save()
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_revenue_dashboard_renders_for_admin(auth_admin):
    Client.objects.create(
        name="A",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )
    resp = auth_admin.get(reverse("portal:revenue_dashboard"))
    assert resp.status_code == 200
    assert b"Current MRR" in resp.content


@pytest.mark.django_db
def test_revenue_metrics_api_admin_only(engineer_user):
    from rest_framework.test import APIClient

    api = APIClient()
    api.force_authenticate(engineer_user)
    resp = api.get("/api/v1/billing/revenue/")
    # Engineer (non-admin) → 403 via IsAdmin
    assert resp.status_code == 403


@pytest.mark.django_db
def test_revenue_metrics_api_returns_data(admin_user):
    from rest_framework.test import APIClient

    Client.objects.create(
        name="A",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )
    api = APIClient()
    api.force_authenticate(admin_user)
    resp = api.get("/api/v1/billing/revenue/")
    assert resp.status_code == 200
    assert Decimal(resp.data["current_mrr"]) == Decimal("30")
    assert "history" in resp.data
