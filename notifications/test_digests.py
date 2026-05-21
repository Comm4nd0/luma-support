"""Friday weekly digest — per-client signal aggregation + send loop."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from clients.models import Contact
from notifications.digests import compose_for, send_digests
from notifications.tasks import send_weekly_client_digest
from tickets.models import Ticket, TimeEntry

pytestmark = pytest.mark.django_db


def test_no_signal_means_zero_stats(client_record):
    stats = compose_for(client_record)
    assert stats.opened == 0
    assert stats.closed == 0
    assert stats.hours_logged == Decimal("0.0")
    assert stats.has_signal is False


def test_recent_tickets_and_time_show_up(client_record, engineer_user):
    now = timezone.now()
    Ticket.objects.create(client=client_record, subject="recent")
    t = Ticket.objects.create(client=client_record, subject="closed")
    Ticket.objects.filter(pk=t.pk).update(
        status=Ticket.Status.CLOSED,
        resolved_at=now - timedelta(days=2),
    )
    TimeEntry.objects.create(ticket=t, user=engineer_user, minutes=90)
    stats = compose_for(client_record, now=now)
    assert stats.opened == 2
    assert stats.closed == 1
    assert stats.hours_logged == Decimal("1.5")
    assert stats.has_signal is True


def test_send_loop_skips_opt_out(client_record, engineer_user, settings):
    settings.DEFAULT_FROM_EMAIL = "marco@luma.test"
    Ticket.objects.create(client=client_record, subject="x")
    Contact.objects.create(
        client=client_record, name="A", email="a@acme.test", is_primary=True
    )
    client_record.weekly_digest_opt_in = False
    client_record.save()
    assert send_digests() == 0
    assert mail.outbox == []


def test_send_loop_emails_primary_contact(client_record, settings):
    settings.DEFAULT_FROM_EMAIL = "marco@luma.test"
    Ticket.objects.create(client=client_record, subject="x")
    Contact.objects.create(
        client=client_record, name="Primary", email="a@acme.test", is_primary=True
    )
    sent = send_digests()
    assert sent == 1
    assert mail.outbox[0].to == ["a@acme.test"]
    assert "weekly summary" in mail.outbox[0].subject.lower()


def test_celery_task_runs_the_loop(client_record, settings):
    settings.DEFAULT_FROM_EMAIL = "marco@luma.test"
    Ticket.objects.create(client=client_record, subject="x")
    Contact.objects.create(
        client=client_record, name="A", email="a@acme.test", is_primary=True
    )
    out = send_weekly_client_digest()
    assert "1 emails sent" in out
