"""GDPR export + forget."""
import pytest
from rest_framework.test import APIClient

from clients.models import Client, Contact, ClientDocument
from clients.privacy import export_client, forget_client
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def test_export_includes_client_contacts_tickets(admin_user, client_record):
    Contact.objects.create(client=client_record, name="A", email="a@x.test")
    Ticket.objects.create(client=client_record, subject="restore")
    payload = export_client(client_record)
    assert payload["client"]["name"] == client_record.name
    assert any(c["name"] == "A" for c in payload["contacts"])
    assert any(t["subject"] == "restore" for t in payload["tickets"])


def test_export_endpoint_streams_attachment(admin_user, client_record):
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.get(f"/api/v1/clients/clients/{client_record.pk}/gdpr-export/")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/json")
    assert "attachment" in resp["Content-Disposition"]


def test_export_engineer_rejected(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(f"/api/v1/clients/clients/{client_record.pk}/gdpr-export/")
    assert resp.status_code == 403


def test_forget_pseudonymises_and_unlinks_users(admin_user, client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    Contact.objects.create(
        client=client_record, name="Real Name", email="real@a.test"
    )
    User.objects.create_user(
        email="c@a.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    touched = forget_client(client_record)
    client_record.refresh_from_db()
    assert client_record.name.startswith("[redacted")
    assert client_record.email == ""
    contact = client_record.contacts.first()
    assert contact.name.startswith("[redacted")
    user = User.objects.get(email="c@a.test")
    assert user.client_id is None
    assert user.is_active is False
    assert touched["contacts"] == 1
    assert touched["users_unlinked"] == 1


def test_forget_endpoint_requires_confirm(admin_user, client_record):
    c = APIClient()
    c.force_authenticate(admin_user)
    # Wrong confirm string → 400, nothing touched.
    resp = c.post(
        f"/api/v1/clients/clients/{client_record.pk}/gdpr-forget/",
        {"confirm": "nope"}, format="json",
    )
    assert resp.status_code == 400
    client_record.refresh_from_db()
    assert not client_record.name.startswith("[redacted")
    # Correct confirm → 200, fields wiped.
    resp = c.post(
        f"/api/v1/clients/clients/{client_record.pk}/gdpr-forget/",
        {"confirm": str(client_record.pk)}, format="json",
    )
    assert resp.status_code == 200
    client_record.refresh_from_db()
    assert client_record.name.startswith("[redacted")
