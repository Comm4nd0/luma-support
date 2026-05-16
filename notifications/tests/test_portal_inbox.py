"""Tests for the server-rendered portal notifications inbox.

Parity with the mobile NotificationsInboxScreen — both UIs read from the
same Notification model, scope to the current user, support unread-only
filtering, and allow mark-single + mark-all-read.
"""
import pytest
from django.urls import reverse

from notifications.models import Notification


@pytest.fixture
def make_notifs(db):
    def _make(user, count, **kwargs):
        return [
            Notification.objects.create(
                user=user,
                type=Notification.Type.TICKET_UPDATE,
                title=f"Update {i}",
                body=f"Body {i}",
                **kwargs,
            )
            for i in range(count)
        ]

    return _make


@pytest.mark.django_db
def test_inbox_requires_login(client):
    resp = client.get(reverse("portal:notifications"))
    assert resp.status_code == 302
    assert "/login" in resp["Location"]


@pytest.mark.django_db
def test_inbox_only_shows_current_users_notifications(
    client, admin_user, engineer_user, make_notifs
):
    make_notifs(admin_user, 2)
    make_notifs(engineer_user, 3)

    client.force_login(admin_user)
    resp = client.get(reverse("portal:notifications"))
    assert resp.status_code == 200
    assert len(resp.context["notifications"]) == 2


@pytest.mark.django_db
def test_unread_filter(client, admin_user, make_notifs):
    make_notifs(admin_user, 2)
    make_notifs(admin_user, 1, read=True)

    client.force_login(admin_user)
    resp = client.get(reverse("portal:notifications") + "?unread=1")
    assert resp.status_code == 200
    assert len(resp.context["notifications"]) == 2
    assert resp.context["unread_count"] == 2


@pytest.mark.django_db
def test_mark_all_read(client, admin_user, make_notifs):
    make_notifs(admin_user, 3)
    assert Notification.objects.filter(user=admin_user, read=False).count() == 3

    client.force_login(admin_user)
    resp = client.post(reverse("portal:notifications_mark_all_read"))
    assert resp.status_code == 302
    assert Notification.objects.filter(user=admin_user, read=False).count() == 0


@pytest.mark.django_db
def test_mark_single_read_redirects_to_ticket_when_linked(
    client, admin_user, make_notifs, client_record
):
    from tickets.models import Ticket

    ticket = Ticket.objects.create(
        client=client_record,
        subject="Broken",
        description="…",
        priority="medium",
    )
    notifs = make_notifs(admin_user, 1)
    notif = notifs[0]
    notif.related_ticket = ticket
    notif.save(update_fields=["related_ticket"])

    client.force_login(admin_user)
    resp = client.post(
        reverse("portal:notification_mark_read", args=[notif.pk])
    )
    assert resp.status_code == 302
    assert f"/tickets/{ticket.pk}" in resp["Location"]
    notif.refresh_from_db()
    assert notif.read is True


@pytest.mark.django_db
def test_cannot_mark_another_users_notification(
    client, admin_user, engineer_user, make_notifs
):
    notifs = make_notifs(engineer_user, 1)
    notif = notifs[0]

    client.force_login(admin_user)
    resp = client.post(
        reverse("portal:notification_mark_read", args=[notif.pk])
    )
    assert resp.status_code == 404
    notif.refresh_from_db()
    assert notif.read is False


@pytest.mark.django_db
def test_unread_count_in_base_context(client, admin_user, make_notifs):
    make_notifs(admin_user, 2)
    make_notifs(admin_user, 1, read=True)

    client.force_login(admin_user)
    resp = client.get(reverse("portal:dashboard"))
    # Context processor exposes the badge value to every template.
    assert resp.context["unread_notifications_count"] == 2
