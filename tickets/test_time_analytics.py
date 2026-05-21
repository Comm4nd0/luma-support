"""Time-tracking analytics endpoint."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from tickets.models import Ticket, TimeEntry

pytestmark = pytest.mark.django_db


def _entry(ticket, user, minutes, billable=True, invoice_line=None):
    return TimeEntry.objects.create(
        ticket=ticket, user=user, minutes=minutes,
        billable=billable, invoice_line=invoice_line,
    )


def test_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="ta@acme.test", password="x",
        role=User.Role.CLIENT, client=client_record,
    )
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.get("/api/v1/tickets/tickets/time-analytics/")
    assert resp.status_code == 403


def test_aggregates_billable_invoiced_unbilled(engineer_user, client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    _entry(t, engineer_user, 60, billable=True)
    _entry(t, engineer_user, 30, billable=True)
    _entry(t, engineer_user, 15, billable=False)
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/tickets/tickets/time-analytics/?group_by=client")
    body = resp.json()
    assert body["totals"]["billable_minutes"] == 90
    assert body["totals"]["non_billable_minutes"] == 15
    # Nothing invoiced yet.
    assert body["totals"]["invoiced_minutes"] == 0
    assert body["totals"]["unbilled_minutes"] == 90
    row = body["rows"][0]
    assert row["billable"] == 90


def test_group_by_user(engineer_user, admin_user, client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    _entry(t, engineer_user, 60)
    _entry(t, admin_user, 30)
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/tickets/tickets/time-analytics/?group_by=user")
    body = resp.json()
    assert body["group_by"] == "user"
    by_label = {r["label"]: r["billable"] for r in body["rows"]}
    assert by_label[engineer_user.email] == 60
    assert by_label[admin_user.email] == 30


def test_window_filter(engineer_user, client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    old = _entry(t, engineer_user, 60)
    TimeEntry.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=60)
    )
    _entry(t, engineer_user, 30)
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/tickets/tickets/time-analytics/?group_by=client")
    # Default window is 30 days, so old entry doesn't show up.
    assert resp.json()["totals"]["billable_minutes"] == 30
