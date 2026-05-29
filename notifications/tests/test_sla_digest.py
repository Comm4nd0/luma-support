"""Daily SLA risk digest task."""
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from notifications.models import Notification
from notifications.tasks import send_sla_risk_digest
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _set_deadline(ticket, when):
    """Set sla_deadline directly, bypassing the save-time auto-derivation."""
    Ticket.objects.filter(pk=ticket.pk).update(sla_deadline=when)


def test_digest_emails_admins_and_creates_notifications(admin_user, client_record):
    now = timezone.now()
    breached = Ticket.objects.create(
        client=client_record, subject="overdue", priority="high"
    )
    _set_deadline(breached, now - timedelta(hours=1))
    approaching = Ticket.objects.create(
        client=client_record, subject="soon", priority="medium"
    )
    _set_deadline(approaching, now + timedelta(hours=2))
    # Far-future: outside the 8h window, must be excluded.
    safe = Ticket.objects.create(
        client=client_record, subject="fine", priority="low"
    )
    _set_deadline(safe, now + timedelta(days=3))

    result = send_sla_risk_digest()

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert admin_user.email in msg.to
    assert f"#{breached.pk}" in msg.body
    assert f"#{approaching.pk}" in msg.body
    assert f"#{safe.pk}" not in msg.body
    assert "BREACHED" in msg.body
    # One in-app notification per admin (parity with mobile inbox / portal alerts).
    assert Notification.objects.filter(
        user=admin_user, type=Notification.Type.SYSTEM_ALERT
    ).exists()
    assert "emailed 1 admins" in result


def test_digest_noops_when_nothing_at_risk(admin_user, client_record):
    safe = Ticket.objects.create(
        client=client_record, subject="fine", priority="low"
    )
    _set_deadline(safe, timezone.now() + timedelta(days=5))

    result = send_sla_risk_digest()

    assert mail.outbox == []
    assert "skipped" in result
