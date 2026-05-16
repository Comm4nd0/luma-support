"""MaintenanceSchedule model + generate_scheduled_tickets Celery task."""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from tickets.models import MaintenanceSchedule, Ticket
from tickets.tasks import generate_scheduled_tickets

pytestmark = pytest.mark.django_db


def _sched(
    client,
    cadence=MaintenanceSchedule.Cadence.MONTHLY,
    *,
    next_run_at=None,
    subject="Quarterly health check",
    priority="",
    active=True,
):
    return MaintenanceSchedule.objects.create(
        client=client,
        cadence=cadence,
        next_run_at=next_run_at or timezone.localdate(),
        template_subject=subject,
        template_description="Standard maintenance pass.",
        priority=priority,
        active=active,
    )


# ----- cadence math -----------------------------------------------------


def test_compute_next_run_at_weekly(client_record):
    s = _sched(
        client_record,
        cadence=MaintenanceSchedule.Cadence.WEEKLY,
        next_run_at=date(2026, 5, 1),
    )
    assert s.compute_next_run_at() == date(2026, 5, 8)


def test_compute_next_run_at_monthly(client_record):
    s = _sched(
        client_record,
        cadence=MaintenanceSchedule.Cadence.MONTHLY,
        next_run_at=date(2026, 1, 31),
    )
    # Feb clamps to the 28th in 2026 (non-leap).
    assert s.compute_next_run_at() == date(2026, 2, 28)


def test_compute_next_run_at_quarterly_annual(client_record):
    s = _sched(
        client_record,
        cadence=MaintenanceSchedule.Cadence.QUARTERLY,
        next_run_at=date(2026, 5, 16),
    )
    assert s.compute_next_run_at() == date(2026, 8, 16)
    s.cadence = MaintenanceSchedule.Cadence.ANNUAL
    assert s.compute_next_run_at() == date(2027, 5, 16)


# ----- task -------------------------------------------------------------


def test_due_schedule_creates_ticket_and_advances(client_record):
    today = timezone.localdate()
    s = _sched(
        client_record,
        cadence=MaintenanceSchedule.Cadence.MONTHLY,
        next_run_at=today - timedelta(days=1),
        subject="Network audit",
    )
    result = generate_scheduled_tickets()
    assert "1 created" in result
    assert Ticket.objects.filter(client=client_record).count() == 1
    t = Ticket.objects.get(client=client_record)
    assert t.subject == "Network audit"
    s.refresh_from_db()
    assert s.last_run_at == today
    assert s.next_run_at > today


def test_inactive_schedule_does_nothing(client_record):
    today = timezone.localdate()
    _sched(
        client_record,
        next_run_at=today - timedelta(days=2),
        active=False,
    )
    generate_scheduled_tickets()
    assert Ticket.objects.count() == 0


def test_future_schedule_does_nothing(client_record):
    today = timezone.localdate()
    _sched(client_record, next_run_at=today + timedelta(days=7))
    generate_scheduled_tickets()
    assert Ticket.objects.count() == 0


def test_long_neglected_schedule_advances_past_today(client_record):
    """A monthly schedule overdue by 5 months creates one ticket and lands in
    the future — not 5 tickets, not still overdue."""
    today = timezone.localdate()
    s = _sched(
        client_record,
        cadence=MaintenanceSchedule.Cadence.MONTHLY,
        next_run_at=today - timedelta(days=150),
    )
    generate_scheduled_tickets()
    assert Ticket.objects.count() == 1
    s.refresh_from_db()
    assert s.next_run_at > today


def test_priority_inherits_when_blank(client_record):
    """Blank priority on the schedule → Ticket._auto_priority kicks in."""
    today = timezone.localdate()
    _sched(
        client_record,
        next_run_at=today,
        priority="",  # blank — should auto-derive from care plan tier
    )
    generate_scheduled_tickets()
    t = Ticket.objects.get()
    # client_record fixture has care_plan_tier=PROFESSIONAL → medium
    assert t.priority == Ticket.Priority.MEDIUM
