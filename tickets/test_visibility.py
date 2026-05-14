"""Visibility / scoping tests for the ticketing and client APIs + portal.

Rule:
    - Staff (role admin/engineer) and Django superusers see everything.
    - Client-role users see only data tied to their own Client.
    - A user without an associated Client and without staff privileges sees nothing.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from clients.models import CarePlanTier, Client, Contact, System, SystemType
from tickets.models import Ticket, TicketNote


@pytest.fixture
def other_client(db):
    return Client.objects.create(
        name="Other Client",
        company="Other Co",
        email="other@example.com",
        care_plan_tier=CarePlanTier.ESSENTIAL,
    )


@pytest.fixture
def client_user(db, client_record):
    User = get_user_model()
    return User.objects.create_user(
        email="customer@example.com",
        password="password123",
        role="client",
        client=client_record,
    )


@pytest.fixture
def orphan_client_user(db):
    """Client-role user with no linked Client."""
    User = get_user_model()
    return User.objects.create_user(
        email="orphan@example.com",
        password="password123",
        role="client",
    )


@pytest.fixture
def two_tickets(db, client_record, other_client):
    own = Ticket.objects.create(client=client_record, subject="Own ticket")
    other = Ticket.objects.create(client=other_client, subject="Other ticket")
    return own, other


# --- API: Tickets ------------------------------------------------------


@pytest.mark.django_db
def test_api_client_user_only_sees_own_tickets(client_user, two_tickets):
    own, other = two_tickets
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.get("/api/v1/tickets/tickets/")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data["results"]}
    assert own.pk in ids and other.pk not in ids


@pytest.mark.django_db
def test_api_client_user_cannot_retrieve_other_clients_ticket(client_user, two_tickets):
    _, other = two_tickets
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.get(f"/api/v1/tickets/tickets/{other.pk}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_api_engineer_sees_every_ticket(engineer_user, two_tickets):
    api = APIClient()
    api.force_authenticate(engineer_user)
    resp = api.get("/api/v1/tickets/tickets/")
    assert resp.status_code == 200
    assert resp.data["count"] == 2


@pytest.mark.django_db
def test_api_admin_sees_every_ticket(admin_user, two_tickets):
    api = APIClient()
    api.force_authenticate(admin_user)
    resp = api.get("/api/v1/tickets/tickets/")
    assert resp.status_code == 200
    assert resp.data["count"] == 2


@pytest.mark.django_db
def test_api_orphan_client_user_sees_no_tickets(orphan_client_user, two_tickets):
    api = APIClient()
    api.force_authenticate(orphan_client_user)
    resp = api.get("/api/v1/tickets/tickets/")
    assert resp.status_code == 200
    assert resp.data["count"] == 0


@pytest.mark.django_db
def test_api_client_user_create_ticket_forced_to_own_client(
    client_user, client_record, other_client
):
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.post(
        "/api/v1/tickets/tickets/",
        {"client": other_client.pk, "subject": "Sneaky", "priority": "low"},
        format="json",
    )
    assert resp.status_code == 201
    # client was forced to user's own client, not the one they tried to use
    assert resp.data["client"] == client_record.pk


# --- API: Clients / Systems / Contacts ---------------------------------


@pytest.mark.django_db
def test_api_client_user_only_sees_own_client(client_user, client_record, other_client):
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.get("/api/v1/clients/clients/")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data["results"]}
    assert ids == {client_record.pk}


@pytest.mark.django_db
def test_api_client_user_only_sees_own_systems(client_user, client_record, other_client):
    System.objects.create(client=client_record, type=SystemType.NETWORK, name="Own")
    System.objects.create(client=other_client, type=SystemType.NETWORK, name="Theirs")
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.get("/api/v1/clients/systems/")
    assert resp.status_code == 200
    names = {row["name"] for row in resp.data["results"]}
    assert names == {"Own"}


@pytest.mark.django_db
def test_api_client_user_only_sees_own_contacts(client_user, client_record, other_client):
    Contact.objects.create(client=client_record, name="Mine")
    Contact.objects.create(client=other_client, name="Theirs")
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.get("/api/v1/clients/contacts/")
    assert resp.status_code == 200
    names = {row["name"] for row in resp.data["results"]}
    assert names == {"Mine"}


# --- API: Users --------------------------------------------------------


@pytest.mark.django_db
def test_api_client_user_only_sees_users_at_own_client(client_user, client_record):
    User = get_user_model()
    User.objects.create_user(
        email="colleague@example.com",
        password="x",
        role="client",
        client=client_record,
    )
    User.objects.create_user(
        email="stranger@example.com", password="x", role="client",
    )
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.get("/api/v1/accounts/users/")
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.data["results"]}
    assert "customer@example.com" in emails
    assert "colleague@example.com" in emails
    assert "stranger@example.com" not in emails


@pytest.mark.django_db
def test_api_client_user_cannot_create_users(client_user):
    api = APIClient()
    api.force_authenticate(client_user)
    resp = api.post(
        "/api/v1/accounts/users/",
        {"email": "new@example.com", "role": "client"},
        format="json",
    )
    assert resp.status_code in (401, 403)


# --- Portal ------------------------------------------------------------


@pytest.mark.django_db
def test_portal_ticket_list_scoped_for_client_user(client, client_user, two_tickets):
    own, other = two_tickets
    client.force_login(client_user)
    resp = client.get(reverse("portal:ticket_list"))
    assert resp.status_code == 200
    rendered = resp.content.decode()
    assert own.subject in rendered
    assert other.subject not in rendered


@pytest.mark.django_db
def test_portal_ticket_detail_404_for_other_clients_ticket(client, client_user, two_tickets):
    _, other = two_tickets
    client.force_login(client_user)
    resp = client.get(reverse("portal:ticket_detail", args=[other.pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_portal_ticket_detail_hides_internal_notes_for_client(
    client, client_user, client_record
):
    t = Ticket.objects.create(client=client_record, subject="With notes")
    TicketNote.objects.create(ticket=t, body="public reply", internal=False)
    TicketNote.objects.create(ticket=t, body="internal triage", internal=True)
    client.force_login(client_user)
    resp = client.get(reverse("portal:ticket_detail", args=[t.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "public reply" in body
    assert "internal triage" not in body


@pytest.mark.django_db
def test_portal_client_list_scoped_for_client_user(
    client, client_user, client_record, other_client
):
    client.force_login(client_user)
    resp = client.get(reverse("portal:client_list"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert client_record.name in body
    assert other_client.name not in body


@pytest.mark.django_db
def test_portal_client_detail_404_for_other_client(client, client_user, other_client):
    client.force_login(client_user)
    resp = client.get(reverse("portal:client_detail", args=[other_client.pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_portal_client_create_blocked_for_client_user(client, client_user):
    client.force_login(client_user)
    resp = client.get(reverse("portal:client_create"))
    assert resp.status_code == 302
    assert resp.url == reverse("portal:dashboard")


@pytest.mark.django_db
def test_portal_engineer_sees_every_ticket(client, engineer_user, two_tickets):
    own, other = two_tickets
    client.force_login(engineer_user)
    resp = client.get(reverse("portal:ticket_list"))
    body = resp.content.decode()
    assert own.subject in body
    assert other.subject in body


@pytest.mark.django_db
def test_portal_admin_sees_every_client(client, admin_user, client_record, other_client):
    client.force_login(admin_user)
    resp = client.get(reverse("portal:client_list"))
    body = resp.content.decode()
    assert client_record.name in body
    assert other_client.name in body
