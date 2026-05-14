from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from clients.models import CarePlanTier, Client
from tickets.models import Ticket, TimeEntry
from tickets.sla import auto_priority_for, deadline_for


@pytest.mark.django_db
def test_sla_deadline_set_on_create(client_record):
    t = Ticket.objects.create(
        client=client_record, subject="x", priority=Ticket.Priority.HIGH
    )
    assert t.sla_deadline is not None
    delta = t.sla_deadline - t.created_at
    # high = 4 hours, allow second-level slop
    assert abs(delta - timedelta(hours=4)) < timedelta(seconds=2)


@pytest.mark.django_db
def test_resolved_at_set_on_status_transition(client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    assert t.resolved_at is None
    t.transition_to(Ticket.Status.RESOLVED)
    assert t.resolved_at is not None


@pytest.mark.django_db
def test_breached_when_deadline_in_past(client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    Ticket.objects.filter(pk=t.pk).update(sla_deadline=timezone.now() - timedelta(minutes=1))
    t.refresh_from_db()
    assert t.is_breached is True


def test_priority_table_covers_all_tiers():
    for tier in [c[0] for c in CarePlanTier.choices]:
        assert auto_priority_for(tier) in {"critical", "high", "medium", "low"}


def test_deadline_for_uses_priority_table():
    now = timezone.now()
    assert deadline_for(now, "critical") - now == timedelta(hours=2)
    assert deadline_for(now, "low") - now == timedelta(hours=48)


@pytest.mark.django_db
def test_time_entry_cost_uses_client_rate(admin_user, settings):
    settings.DEFAULT_HOURLY_RATE = Decimal("75.00")
    c = Client.objects.create(name="Hi rate", hourly_rate=Decimal("90.00"))
    t = Ticket.objects.create(client=c, subject="x")
    e = TimeEntry.objects.create(ticket=t, user=admin_user, minutes=90)
    assert e.hours() == Decimal("1.50")
    assert e.cost() == Decimal("135.00")


@pytest.mark.django_db
def test_time_entry_cost_falls_back_to_default(admin_user, settings):
    settings.DEFAULT_HOURLY_RATE = Decimal("75.00")
    c = Client.objects.create(name="No rate")
    t = Ticket.objects.create(client=c, subject="x")
    e = TimeEntry.objects.create(ticket=t, user=admin_user, minutes=60)
    assert e.cost() == Decimal("75.00")
