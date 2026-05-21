"""``credentials_present`` flag and the rotation-request endpoint."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from clients.models import System, SystemType
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _client_user(client):
    User = get_user_model()
    return User.objects.create_user(
        email="cv@acme.test", password="x", role=User.Role.CLIENT, client=client
    )


def test_credentials_present_false_when_empty(client_record, engineer_user):
    s = System.objects.create(client=client_record, name="UniFi", type=SystemType.NETWORK)
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(f"/api/v1/clients/systems/{s.pk}/")
    assert resp.json()["credentials_present"] is False


def test_credentials_present_true_after_set(client_record, engineer_user):
    s = System.objects.create(client=client_record, name="UniFi", type=SystemType.NETWORK)
    s.set_credentials("hunter2")
    s.save()
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(f"/api/v1/clients/systems/{s.pk}/")
    assert resp.json()["credentials_present"] is True
    # Plaintext never echoed back.
    assert "hunter2" not in resp.content.decode()


def test_client_can_request_rotation_opens_ticket(client_record):
    s = System.objects.create(client=client_record, name="UniFi", type=SystemType.NETWORK)
    cu = _client_user(client_record)
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.post(f"/api/v1/clients/systems/{s.pk}/request-credential-rotation/")
    assert resp.status_code == 201
    tid = resp.json()["ticket_id"]
    t = Ticket.objects.get(pk=tid)
    assert "rotate credentials" in t.subject.lower()
    assert t.client_id == client_record.pk
    assert t.system_id == s.pk
