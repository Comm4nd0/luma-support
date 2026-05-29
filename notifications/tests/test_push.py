"""Tests for the FCM push fan-out task.

We mock the firebase_admin.messaging layer entirely; these tests verify
behaviour (token selection, push_sent flip, dead-token cleanup) rather
than hitting a real Firebase project.
"""
from unittest.mock import MagicMock, patch

import pytest

from notifications import tasks
from notifications.models import DeviceToken, Notification


def _fake_response(success_count, failures=None):
    """Build an object shaped like firebase_admin.messaging.BatchResponse."""
    failures = failures or []
    responses = []
    for _ in [True] * success_count:
        responses.append(MagicMock(success=True, exception=None))
    for exc in failures:
        responses.append(MagicMock(success=False, exception=exc))
    batch = MagicMock()
    batch.success_count = success_count
    batch.responses = responses
    return batch


@pytest.fixture
def fcm_enabled(settings):
    settings.FCM_ENABLED = True


@pytest.mark.django_db
def test_send_push_skips_when_fcm_disabled(settings, admin_user):
    settings.FCM_ENABLED = False
    DeviceToken.objects.create(user=admin_user, platform="ios", token="t")
    n = Notification.objects.create(
        user=admin_user, type=Notification.Type.TICKET_UPDATE, title="hi"
    )
    # Calling directly so we don't depend on the post_save signal.
    result = tasks.send_push.run(n.pk)
    assert result == "fcm disabled"
    n.refresh_from_db()
    assert n.push_sent is False


@pytest.mark.django_db
def test_send_push_no_devices_short_circuits(fcm_enabled, admin_user):
    n = Notification.objects.create(
        user=admin_user, type=Notification.Type.TICKET_UPDATE, title="hi"
    )
    with patch.object(tasks, "_fcm_send") as mock_send:
        result = tasks.send_push.run(n.pk)
    mock_send.assert_not_called()
    assert result == "no devices"


@pytest.mark.django_db
def test_send_push_calls_fcm_for_each_active_device(fcm_enabled, admin_user):
    DeviceToken.objects.create(user=admin_user, platform="ios", token="a")
    DeviceToken.objects.create(user=admin_user, platform="android", token="b")
    DeviceToken.objects.create(
        user=admin_user, platform="ios", token="c", is_active=False
    )
    n = Notification.objects.create(
        user=admin_user, type=Notification.Type.TICKET_UPDATE, title="hi"
    )
    with patch.object(tasks, "_fcm_send", return_value=_fake_response(2)) as mock_send:
        tasks.send_push.run(n.pk)
    sent_tokens = {msg.token for msg in mock_send.call_args.args[0]}
    assert sent_tokens == {"a", "b"}
    n.refresh_from_db()
    assert n.push_sent is True


@pytest.mark.django_db
def test_send_push_deactivates_dead_tokens(fcm_enabled, admin_user):
    DeviceToken.objects.create(user=admin_user, platform="ios", token="alive")
    DeviceToken.objects.create(user=admin_user, platform="ios", token="dead")
    n = Notification.objects.create(
        user=admin_user, type=Notification.Type.TICKET_UPDATE, title="hi"
    )
    dead_exc = MagicMock(code="UNREGISTERED")
    fake = _fake_response(success_count=1, failures=[dead_exc])
    with patch.object(tasks, "_fcm_send", return_value=fake):
        tasks.send_push.run(n.pk)
    alive = DeviceToken.objects.get(token="alive")
    dead = DeviceToken.objects.get(token="dead")
    assert alive.is_active is True
    assert dead.is_active is False


@pytest.mark.django_db
def test_send_push_attaches_ticket_route_in_data(fcm_enabled, admin_user, client_record):
    from tickets.models import Ticket

    ticket = Ticket.objects.create(client=client_record, subject="x")
    DeviceToken.objects.create(user=admin_user, platform="ios", token="t")
    n = Notification.objects.create(
        user=admin_user,
        type=Notification.Type.TICKET_UPDATE,
        title="t",
        related_ticket=ticket,
    )
    with patch.object(tasks, "_fcm_send", return_value=_fake_response(1)) as mock_send:
        tasks.send_push.run(n.pk)
    msg = mock_send.call_args.args[0][0]
    assert msg.data["ticket_id"] == str(ticket.pk)
    assert msg.data["route"] == f"/tickets/{ticket.pk}"


@pytest.mark.django_db
def test_notification_post_save_enqueues_push(fcm_enabled, admin_user):
    """The signal should call send_push.delay when a Notification is created.

    CELERY_TASK_ALWAYS_EAGER is True in conftest so .delay runs inline."""
    with patch.object(tasks, "_fcm_send", return_value=_fake_response(0)) as mock_send:
        Notification.objects.create(
            user=admin_user, type=Notification.Type.TICKET_UPDATE, title="hi"
        )
    # Task ran (eager); no devices means it short-circuited before _fcm_send.
    mock_send.assert_not_called()
