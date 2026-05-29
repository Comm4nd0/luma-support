"""GDPR export + forget."""
import pytest
from django.contrib.auth import get_user_model
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient

from clients.models import Client, ClientDocument, Contact, SiteVisit
from clients.privacy import export_client, forget_client
from tickets.models import Ticket, TicketNote, TimeEntry

pytestmark = pytest.mark.django_db


def test_export_includes_client_contacts_tickets(admin_user, client_record):
    Contact.objects.create(client=client_record, name="A", email="a@x.test")
    Ticket.objects.create(client=client_record, subject="restore")
    payload = export_client(client_record)
    assert payload["client"]["name"] == client_record.name
    assert any(c["name"] == "A" for c in payload["contacts"])
    assert any(t["subject"] == "restore" for t in payload["tickets"])


def _populate(client, engineer, n):
    """Create ``n`` of each related row that the export walks."""
    for i in range(n):
        ticket = Ticket.objects.create(client=client, subject=f"t{i}")
        TicketNote.objects.create(ticket=ticket, author=engineer, body="note")
        TimeEntry.objects.create(ticket=ticket, user=engineer, minutes=15)
        ClientDocument.objects.create(
            client=client, title=f"doc{i}", file="x.txt", uploaded_by=engineer
        )
        SiteVisit.objects.create(client=client, user=engineer)


def test_export_query_count_is_constant(client_record, engineer_user):
    """Export must not issue per-row FK queries (no N+1).

    The query count is compared across two dataset sizes: with the
    select_related/prefetch_related in place it stays flat, whereas an
    N+1 (one query per note author, time-entry user, document uploader,
    site-visit user) would grow with the row count.
    """
    User = get_user_model()
    small_client = client_record
    _populate(small_client, engineer_user, 1)

    big_engineer = User.objects.create_user(
        email="eng2@example.com", password="x", role="engineer"
    )
    big_client = Client.objects.create(
        name="Big", company="Big Co", email="big@test.example.com"
    )
    _populate(big_client, big_engineer, 5)

    with CaptureQueriesContext(connection) as small:
        export_client(small_client)
    with CaptureQueriesContext(connection) as big:
        export_client(big_client)

    assert len(big.captured_queries) == len(small.captured_queries)


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
