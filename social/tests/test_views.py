"""API: list/inbox + dismiss + convert-to-ticket."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditLog
from social.models import (
    InboxStatus,
    Platform,
    SocialAccount,
    SocialInboxItem,
)
from tickets.models import Ticket


@pytest.fixture
def account(db, admin_user):
    a = SocialAccount.objects.create(
        platform=Platform.FACEBOOK_PAGE,
        external_id="fb-1",
        display_name="Luma FB",
        connected_by=admin_user,
    )
    a.set_access_token("t")
    a.save()
    return a


@pytest.fixture
def open_dm(db, account):
    return SocialInboxItem.objects.create(
        account=account,
        kind="dm",
        external_id="m-1",
        author_handle="alice",
        author_display="Alice Example",
        preview="Do you fix wifi?",
        permalink="https://example.com/m-1",
        received_at=timezone.now() - timedelta(minutes=30),
        status=InboxStatus.OPEN,
    )


@pytest.mark.django_db
def test_inbox_list_requires_staff(open_dm, db):
    from django.contrib.auth import get_user_model

    client_user = get_user_model().objects.create_user(
        email="c@example.com", password="pw1!", role="client"
    )
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.get("/api/v1/social/inbox/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_dismiss_inbox_item(open_dm, engineer_user):
    api = APIClient()
    api.force_authenticate(engineer_user)
    resp = api.post(f"/api/v1/social/inbox/{open_dm.pk}/dismiss/")
    assert resp.status_code == 200
    open_dm.refresh_from_db()
    assert open_dm.status == InboxStatus.DISMISSED
    assert AuditLog.objects.filter(action="social.inbox_dismiss").exists()


@pytest.mark.django_db
def test_convert_to_ticket_creates_ticket_and_lead_client(open_dm, admin_user):
    api = APIClient()
    api.force_authenticate(admin_user)
    resp = api.post(f"/api/v1/social/inbox/{open_dm.pk}/convert-to-ticket/")
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]
    ticket = Ticket.objects.get(pk=ticket_id)
    assert ticket.created_by == admin_user
    assert ticket.client.name.startswith("Social lead:")
    open_dm.refresh_from_db()
    assert open_dm.status == InboxStatus.CONVERTED
    assert open_dm.converted_ticket_id == ticket.pk
    assert AuditLog.objects.filter(action="social.inbox_convert").exists()


@pytest.mark.django_db
def test_convert_to_ticket_with_explicit_client(open_dm, admin_user, client_record):
    api = APIClient()
    api.force_authenticate(admin_user)
    resp = api.post(
        f"/api/v1/social/inbox/{open_dm.pk}/convert-to-ticket/",
        {"client_id": client_record.pk},
        format="json",
    )
    assert resp.status_code == 200
    ticket = Ticket.objects.get(pk=resp.json()["ticket_id"])
    assert ticket.client_id == client_record.pk


@pytest.mark.django_db
def test_convert_to_ticket_is_idempotent(open_dm, admin_user):
    api = APIClient()
    api.force_authenticate(admin_user)
    first = api.post(f"/api/v1/social/inbox/{open_dm.pk}/convert-to-ticket/")
    second = api.post(f"/api/v1/social/inbox/{open_dm.pk}/convert-to-ticket/")
    assert first.json()["ticket_id"] == second.json()["ticket_id"]


@pytest.mark.django_db
def test_inbox_status_filter(account, engineer_user):
    SocialInboxItem.objects.create(
        account=account, kind="dm", external_id="a",
        received_at=timezone.now(), status=InboxStatus.OPEN,
    )
    SocialInboxItem.objects.create(
        account=account, kind="dm", external_id="b",
        received_at=timezone.now(), status=InboxStatus.DISMISSED,
    )
    api = APIClient()
    api.force_authenticate(engineer_user)
    resp = api.get("/api/v1/social/inbox/?status=open")
    assert resp.status_code == 200
    ids = {r["external_id"] for r in resp.json()["results"]}
    assert ids == {"a"}
