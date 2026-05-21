"""Tests for the Slack / Teams / generic outbound webhook channel."""
from unittest.mock import patch

import pytest

from notifications.models import Notification, OutboundWebhook
from notifications.tasks import send_outbound_webhook

pytestmark = pytest.mark.django_db


def _notif(user):
    return Notification.objects.create(
        user=user,
        type=Notification.Type.SLA_WARNING,
        title="SLA approaching",
        body="Ticket #42 due in 25 minutes.",
    )


def test_slack_format_payload(admin_user):
    OutboundWebhook.objects.create(
        user=admin_user,
        name="My Slack",
        url="https://hooks.slack.example/T/B/x",
        format=OutboundWebhook.Format.SLACK,
    )
    notif = _notif(admin_user)
    captured = {}

    class FakeResp:
        status_code = 200

    def fake_post(url, json=None, timeout=None):  # noqa: A002
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    with patch("httpx.post", side_effect=fake_post):
        out = send_outbound_webhook(notif.pk)

    assert out == "outbound webhooks: 1 attempted"
    assert captured["url"].startswith("https://hooks.slack.example/")
    assert "SLA approaching" in captured["json"]["text"]


def test_event_filter_skips_non_matching_types(admin_user):
    OutboundWebhook.objects.create(
        user=admin_user,
        name="critical-only",
        url="https://example.test/x",
        event_filter=[Notification.Type.NEW_TICKET],
    )
    notif = _notif(admin_user)  # type = SLA_WARNING
    with patch("httpx.post") as post:
        send_outbound_webhook(notif.pk)
    post.assert_not_called()


def test_failure_records_last_status_but_does_not_raise(admin_user):
    hook = OutboundWebhook.objects.create(
        user=admin_user, name="bad", url="https://no.dns.example/x"
    )
    notif = _notif(admin_user)
    with patch("httpx.post", side_effect=RuntimeError("boom")):
        # Must not raise.
        send_outbound_webhook(notif.pk)
    hook.refresh_from_db()
    assert hook.last_status.startswith("err:")
    assert hook.last_called_at is not None


def test_disabled_hook_is_skipped(admin_user):
    OutboundWebhook.objects.create(
        user=admin_user, name="off", url="https://x.test/", enabled=False
    )
    notif = _notif(admin_user)
    with patch("httpx.post") as post:
        send_outbound_webhook(notif.pk)
    post.assert_not_called()
