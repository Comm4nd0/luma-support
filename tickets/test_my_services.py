"""MyServicesView — client-facing view of their own Systems and open tickets."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.urls import reverse
from django.utils import timezone

from clients.models import CarePlanTier, Client, System, SystemType
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _client_user(email, *, client=None):
    User = get_user_model()
    return User.objects.create_user(
        email=email, password="x", role=User.Role.CLIENT, client=client,
    )


def test_anonymous_user_is_redirected_to_login():
    resp = DjangoClient().get(reverse("portal:my_services"))
    assert resp.status_code == 302
    assert "/login/" in resp.url


def test_user_without_client_is_redirected_to_dashboard(engineer_user):
    """Engineers/admins aren't linked to a single client — bounce them."""
    client = DjangoClient()
    client.force_login(engineer_user)
    resp = client.get(reverse("portal:my_services"))
    assert resp.status_code == 302
    assert reverse("portal:dashboard") in resp.url


def test_client_user_sees_only_own_systems(client_record):
    other = Client.objects.create(name="Other Co", care_plan_tier=CarePlanTier.NONE)
    System.objects.create(
        client=client_record, type=SystemType.NETWORK, name="My WiFi",
        health_status="ok", last_checked_at=timezone.now(),
    )
    System.objects.create(
        client=other, type=SystemType.NETWORK, name="Their WiFi",
        health_status="down",
    )

    user = _client_user("alice@acme.test", client=client_record)
    client = DjangoClient()
    client.force_login(user)
    resp = client.get(reverse("portal:my_services"))

    assert resp.status_code == 200
    assert b"My WiFi" in resp.content
    assert b"Their WiFi" not in resp.content


def test_open_tickets_for_own_systems_are_listed(client_record):
    sys_ = System.objects.create(
        client=client_record, type=SystemType.NETWORK, name="WiFi",
    )
    Ticket.objects.create(
        client=client_record, system=sys_, subject="Speed slow",
    )
    Ticket.objects.create(
        client=client_record, system=sys_, subject="Old issue",
        status=Ticket.Status.CLOSED,
    )

    user = _client_user("alice@acme.test", client=client_record)
    client = DjangoClient()
    client.force_login(user)
    resp = client.get(reverse("portal:my_services"))

    assert resp.status_code == 200
    assert b"Speed slow" in resp.content
    # Closed tickets shouldn't appear in the "open" list.
    assert b"Old issue" not in resp.content
