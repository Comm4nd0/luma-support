"""Tests for the after-hours autoresponder."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from features.models import FeatureFlag
from tickets.models import Ticket
from tickets.tasks import after_hours_acknowledge, is_after_hours

pytestmark = pytest.mark.django_db


# Use a fixed zoneinfo so the test isn't sensitive to host TZ.
_LON = ZoneInfo("Europe/London")


def _at(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=_LON)


def test_business_hours_weekday_is_not_after_hours():
    # Wed 14:00 — middle of the day.
    assert is_after_hours(_at(5, 20, 14)) is False


def test_evening_weekday_is_after_hours():
    # Wed 22:30 — clearly after hours.
    assert is_after_hours(_at(5, 20, 22, 30)) is True


def test_weekend_is_after_hours_even_during_business_hours():
    # Sat 14:00.
    assert is_after_hours(_at(5, 23, 14)) is True


def test_naive_datetime_treated_as_after_hours():
    naive = datetime(2026, 5, 20, 14)
    assert is_after_hours(naive) is True


def test_task_no_op_when_flag_disabled(client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    assert after_hours_acknowledge(t.pk) == "after_hours_oncall disabled"
    assert t.notes.count() == 0


def test_task_acknowledges_after_hours_ticket(client_record, settings):
    settings.ANTHROPIC_API_KEY = ""  # use the canned fallback message
    # Create the ticket first (signal fires a no-op because the flag is off),
    # then enable the flag and invoke the task explicitly to assert behaviour.
    t = Ticket.objects.create(client=client_record, subject="x")
    Ticket.objects.filter(pk=t.pk).update(
        created_at=_at(5, 23, 23, 0).astimezone(UTC)
    )
    FeatureFlag.objects.create(name="after_hours_oncall", enabled=True)
    assert after_hours_acknowledge(t.pk) == "acknowledged"
    t.refresh_from_db()
    public = t.notes.filter(internal=False)
    internal = t.notes.filter(internal=True)
    assert public.count() == 1
    assert "outside our usual hours" in public.first().body
    assert internal.filter(body__icontains="after-hours auto-acknowledged").exists()


def test_in_business_hours_ticket_is_skipped(client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    Ticket.objects.filter(pk=t.pk).update(
        created_at=_at(5, 20, 14, 0).astimezone(UTC)
    )
    FeatureFlag.objects.create(name="after_hours_oncall", enabled=True)
    assert after_hours_acknowledge(t.pk) == "in business hours — no-op"


def test_critical_after_hours_wakes_engineers(
    client_record, engineer_user, admin_user
):
    from notifications.models import Notification

    t = Ticket.objects.create(
        client=client_record, subject="DOWN", priority=Ticket.Priority.CRITICAL
    )
    Ticket.objects.filter(pk=t.pk).update(
        created_at=_at(5, 23, 22, 0).astimezone(UTC)
    )
    FeatureFlag.objects.create(name="after_hours_oncall", enabled=True)
    # Clear any notifications produced by the create-time signal (CRITICAL
    # tickets fan out via send_ticket_update_email regardless of the flag).
    Notification.objects.filter(related_ticket=t).delete()
    after_hours_acknowledge(t.pk)
    notifs = Notification.objects.filter(related_ticket=t)
    recipients = {n.user_id for n in notifs}
    # Both engineer and admin get an after-hours critical alert.
    assert engineer_user.pk in recipients
    assert admin_user.pk in recipients
