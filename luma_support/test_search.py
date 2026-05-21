"""Cmd-K /api/v1/search/ endpoint."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from knowledge.models import Article
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def test_short_query_returns_empty(engineer_user):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/search/?q=a")
    assert resp.json() == {"results": []}


def test_search_returns_ticket_client_kb(engineer_user, client_record):
    Ticket.objects.create(client=client_record, subject="UniFi outage at HQ")
    Article.objects.create(
        title="UniFi reboot procedure", content="x",
        published_at=timezone.now(),
        visibility=Article.Visibility.ALL_CLIENTS,
    )
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/search/?q=unifi")
    types = {r["type"] for r in resp.json()["results"]}
    assert "ticket" in types
    assert "kb" in types


def test_ticket_id_match(engineer_user, client_record):
    t = Ticket.objects.create(client=client_record, subject="abc")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(f"/api/v1/search/?q=%23{t.pk}")
    labels = [r["label"] for r in resp.json()["results"]]
    assert any(f"#{t.pk}" in label for label in labels)


def test_client_user_only_sees_own_tickets(client_record):
    from clients.models import Client

    User = get_user_model()
    other = Client.objects.create(name="Other co")
    Ticket.objects.create(client=client_record, subject="mine wifi")
    Ticket.objects.create(client=other, subject="other wifi")
    cu = User.objects.create_user(
        email="cs@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.get("/api/v1/search/?q=wifi")
    labels = [r["label"] for r in resp.json()["results"]]
    assert any("mine" in l for l in labels)
    assert not any("other" in l for l in labels)
