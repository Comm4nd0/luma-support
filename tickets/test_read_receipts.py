"""Client read-receipts stamp client_last_viewed_at."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from rest_framework.test import APIClient

from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _client_user(client):
    return get_user_model().objects.create_user(
        email="rr@acme.test", password="x",
        role=get_user_model().Role.CLIENT, client=client,
    )


def test_api_client_view_stamps_receipt(client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    cu = _client_user(client_record)
    c = APIClient()
    c.force_authenticate(cu)
    assert t.client_last_viewed_at is None
    c.get(f"/api/v1/tickets/tickets/{t.pk}/")
    t.refresh_from_db()
    assert t.client_last_viewed_at is not None


def test_api_staff_view_does_not_stamp(client_record, engineer_user):
    t = Ticket.objects.create(client=client_record, subject="x")
    c = APIClient()
    c.force_authenticate(engineer_user)
    c.get(f"/api/v1/tickets/tickets/{t.pk}/")
    t.refresh_from_db()
    assert t.client_last_viewed_at is None


def test_portal_client_view_stamps_receipt(client_record):
    t = Ticket.objects.create(client=client_record, subject="x")
    cu = _client_user(client_record)
    web = DjangoClient()
    web.force_login(cu)
    web.get(f"/tickets/{t.pk}/")
    t.refresh_from_db()
    assert t.client_last_viewed_at is not None


def test_portal_staff_view_does_not_stamp(client_record, engineer_user):
    t = Ticket.objects.create(client=client_record, subject="x")
    web = DjangoClient()
    web.force_login(engineer_user)
    web.get(f"/tickets/{t.pk}/")
    t.refresh_from_db()
    assert t.client_last_viewed_at is None
