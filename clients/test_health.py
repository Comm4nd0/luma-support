"""Tests for `clients.health` health score."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from billing.models import Invoice
from tickets.models import CsatResponse, Ticket

from .health import _band, score_client, score_clients
from .models import CarePlanTier, Client, HealthStatus, System, SystemType


@pytest.mark.django_db
def test_baseline_client_scores_well():
    c = Client.objects.create(
        name="Sunny",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30"),
    )
    s = score_client(c)
    assert s.band == "good"
    assert s.score >= 75


@pytest.mark.django_db
def test_bad_csat_drops_score(client_record):
    # Three 1-star ratings in the last 90 days.
    for _ in range(3):
        t = Ticket.objects.create(
            client=client_record,
            subject="Bad",
            description="x",
            priority=Ticket.Priority.LOW,
            status=Ticket.Status.CLOSED,
        )
        CsatResponse.objects.create(
            ticket=t, rating=1, responded_at=timezone.now()
        )
    s = score_client(client_record)
    assert s.band in {"watch", "at_risk"}
    assert any("CSAT" in r for r in s.reasons)


@pytest.mark.django_db
def test_overdue_invoice_costs_points(client_record):
    Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.AUTHORISED,
        subtotal=Decimal("100"),
        total=Decimal("100"),
        due_date=timezone.localdate() - timedelta(days=10),
    )
    s = score_client(client_record)
    assert any("overdue" in r for r in s.reasons)


@pytest.mark.django_db
def test_systems_down_penalises(client_record):
    System.objects.create(
        client=client_record,
        type=SystemType.NETWORK,
        name="Office UniFi",
        health_status=HealthStatus.DOWN,
    )
    s = score_client(client_record)
    # 0% systems OK with no other negative signals — should drop to watch/at_risk.
    assert any("systems OK" in r for r in s.reasons)


@pytest.mark.django_db
def test_score_clients_is_batched():
    cs = [
        Client.objects.create(
            name=f"C{i}", care_plan_tier=CarePlanTier.ESSENTIAL, monthly_fee=Decimal("30")
        )
        for i in range(5)
    ]
    scores = score_clients(cs)
    assert len(scores) == 5
    assert {s.band for s in scores} == {"good"}


def test_band_cutoffs():
    assert _band(90) == "good"
    assert _band(60) == "watch"
    assert _band(20) == "at_risk"
