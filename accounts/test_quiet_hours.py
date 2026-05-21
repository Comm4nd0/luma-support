"""Quiet-hours suppression on push notifications."""
from datetime import datetime, timezone as _utc
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from notifications.models import DeviceToken, Notification
from notifications.tasks import send_push
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


_LON = ZoneInfo("Europe/London")


def _user(**kwargs):
    User = get_user_model()
    return User.objects.create_user(email="q@luma.test", password="x", **kwargs)


def test_no_window_means_not_in_quiet_hours():
    u = _user()
    assert u.is_in_quiet_hours() is False


def test_simple_window_classifies_local_time():
    u = _user(quiet_hours_start=22, quiet_hours_end=7)
    # 23:00 London = 22:00 UTC (BST in May).
    quiet = datetime(2026, 5, 20, 23, tzinfo=_LON).astimezone(_utc.utc)
    daytime = datetime(2026, 5, 20, 14, tzinfo=_LON).astimezone(_utc.utc)
    assert u.is_in_quiet_hours(quiet) is True
    assert u.is_in_quiet_hours(daytime) is False


def test_simple_non_wraparound_window():
    u = _user(quiet_hours_start=12, quiet_hours_end=14)
    inside = datetime(2026, 5, 20, 13, tzinfo=_LON).astimezone(_utc.utc)
    outside = datetime(2026, 5, 20, 15, tzinfo=_LON).astimezone(_utc.utc)
    assert u.is_in_quiet_hours(inside) is True
    assert u.is_in_quiet_hours(outside) is False


def test_push_suppressed_during_quiet_hours_for_non_critical(client_record, settings):
    settings.FCM_ENABLED = True
    u = _user(quiet_hours_start=0, quiet_hours_end=23, quiet_hours_critical_override=True)
    DeviceToken.objects.create(user=u, platform="ios", token="abc")
    t = Ticket.objects.create(client=client_record, subject="x", priority="medium")
    notif = Notification.objects.create(
        user=u,
        type=Notification.Type.TICKET_UPDATE,
        title="hi",
        related_ticket=t,
    )
    with patch("notifications.tasks._fcm_send") as send:
        out = send_push(notif.pk)
    send.assert_not_called()
    assert "quiet hours" in out


def test_critical_overrides_quiet_hours_by_default(client_record, settings):
    settings.FCM_ENABLED = True
    u = _user(quiet_hours_start=0, quiet_hours_end=23, quiet_hours_critical_override=True)
    DeviceToken.objects.create(user=u, platform="ios", token="abc")
    t = Ticket.objects.create(client=client_record, subject="x", priority="critical")
    notif = Notification.objects.create(
        user=u,
        type=Notification.Type.NEW_TICKET,
        title="DOWN",
        related_ticket=t,
    )

    class _Resp:
        success = True
        exception = None

    class _Bundle:
        responses = [_Resp()]
        success_count = 1

    with patch("notifications.tasks._fcm_send", return_value=_Bundle()) as send:
        out = send_push(notif.pk)
    send.assert_called_once()
    assert "push sent" in out


def test_critical_can_be_silenced_if_override_off(client_record, settings):
    settings.FCM_ENABLED = True
    u = _user(quiet_hours_start=0, quiet_hours_end=23, quiet_hours_critical_override=False)
    DeviceToken.objects.create(user=u, platform="ios", token="abc")
    t = Ticket.objects.create(client=client_record, subject="x", priority="critical")
    notif = Notification.objects.create(
        user=u,
        type=Notification.Type.NEW_TICKET,
        title="DOWN",
        related_ticket=t,
    )
    with patch("notifications.tasks._fcm_send") as send:
        send_push(notif.pk)
    send.assert_not_called()
