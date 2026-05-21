"""Tests for the SLA performance dashboard endpoint + portal page."""
from datetime import timedelta

import pytest
from django.test import Client as DjangoClient
from django.utils import timezone
from rest_framework.test import APIClient

from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _closed(client_record, *, priority, met):
    """Create a ticket that's already closed; mark it SLA-met or breached."""
    t = Ticket.objects.create(
        client=client_record, subject=f"{priority}-{met}", priority=priority
    )
    now = timezone.now()
    deadline = now - timedelta(hours=1)
    resolved = deadline - timedelta(minutes=5) if met else deadline + timedelta(minutes=5)
    Ticket.objects.filter(pk=t.pk).update(
        status=Ticket.Status.CLOSED,
        sla_deadline=deadline,
        resolved_at=resolved,
    )
    return t


def test_sla_analytics_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="cs@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.get("/api/v1/tickets/tickets/sla-analytics/")
    assert resp.status_code == 403


def test_sla_analytics_computes_hit_rate(engineer_user, client_record):
    _closed(client_record, priority="high", met=True)
    _closed(client_record, priority="high", met=True)
    _closed(client_record, priority="high", met=False)
    _closed(client_record, priority="low", met=False)

    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/tickets/tickets/sla-analytics/?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"]["closed"] == 4
    assert body["totals"]["met"] == 2
    assert body["totals"]["breached"] == 2
    assert body["totals"]["hit_rate"] == 0.5

    by_p = {row["priority"]: row for row in body["by_priority"]}
    assert by_p["high"]["closed"] == 3
    assert by_p["high"]["met"] == 2
    assert by_p["high"]["hit_rate"] == round(2 / 3, 3)
    assert by_p["low"]["hit_rate"] == 0.0

    worst = body["worst_clients"]
    assert any(c["client_id"] == client_record.pk for c in worst)


def test_sla_analytics_portal_page(admin_user, client_record):
    _closed(client_record, priority="medium", met=True)
    web = DjangoClient()
    web.force_login(admin_user)
    resp = web.get("/tickets/sla-analytics/")
    assert resp.status_code == 200
    assert b"Hit-rate" in resp.content
