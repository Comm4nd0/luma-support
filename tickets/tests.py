from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from clients.models import CarePlanTier, Client
from tickets.models import Ticket, TicketTag, TimeEntry
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
def test_waiting_status_pauses_sla(client_record):
    t = Ticket.objects.create(
        client=client_record, subject="x", priority=Ticket.Priority.HIGH
    )
    original_deadline = t.sla_deadline
    # Pretend the ticket was created 1 hour ago so a pause has somewhere to go.
    Ticket.objects.filter(pk=t.pk).update(
        sla_deadline=timezone.now() + timedelta(hours=3)
    )
    t.refresh_from_db()
    baseline = t.sla_deadline

    t.transition_to(Ticket.Status.WAITING)
    assert t.is_paused is True
    assert t.is_breached is False
    # Stored deadline doesn't move while paused.
    assert t.sla_deadline == baseline
    # Effective deadline tracks wall-clock past pause start, so the visible
    # countdown stays put (small slop for execution time).
    eff = t.effective_sla_deadline
    assert eff is not None
    assert abs((eff - timezone.now()) - (baseline - t.sla_paused_at)) < timedelta(seconds=2)

    # Simulate 2 hours of waiting on the client.
    Ticket.objects.filter(pk=t.pk).update(
        sla_paused_at=timezone.now() - timedelta(hours=2)
    )
    t.refresh_from_db()
    t.transition_to(Ticket.Status.IN_PROGRESS)
    assert t.is_paused is False
    # Stored deadline has been pushed forward by ~2h.
    assert t.sla_deadline > baseline + timedelta(hours=1, minutes=55)
    assert t.sla_deadline < baseline + timedelta(hours=2, minutes=5)
    # Original deadline still in the future for a fresh high-priority ticket.
    assert original_deadline is not None


@pytest.mark.django_db
def test_paused_tickets_excluded_from_sla_warnings(client_record):
    soon = timezone.now() + timedelta(minutes=5)
    t = Ticket.objects.create(client=client_record, subject="paused")
    Ticket.objects.filter(pk=t.pk).update(
        status=Ticket.Status.WAITING,
        sla_deadline=soon,
        sla_paused_at=timezone.now(),
    )
    other = Ticket.objects.create(client=client_record, subject="live")
    Ticket.objects.filter(pk=other.pk).update(
        status=Ticket.Status.IN_PROGRESS, sla_deadline=soon
    )

    warnings = list(Ticket.objects.sla_warnings())
    assert other in warnings
    paused = Ticket.objects.get(pk=t.pk)
    assert paused not in warnings


@pytest.mark.django_db
def test_ticket_tag_filter_via_slug(client_record):
    unifi = TicketTag.objects.create(name="UniFi", slug="unifi")
    outage = TicketTag.objects.create(name="Outage", slug="outage")
    a = Ticket.objects.create(client=client_record, subject="a")
    a.tags.add(unifi)
    b = Ticket.objects.create(client=client_record, subject="b")
    b.tags.add(unifi, outage)
    c = Ticket.objects.create(client=client_record, subject="c")
    c.tags.add(outage)

    unifi_tickets = Ticket.objects.filter(tags__slug="unifi")
    assert set(unifi_tickets) == {a, b}
    both = Ticket.objects.filter(tags__slug="unifi").filter(tags__slug="outage")
    assert set(both) == {b}


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
