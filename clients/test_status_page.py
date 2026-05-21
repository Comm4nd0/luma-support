"""Public per-client status page."""
import pytest
from django.test import Client as DjangoClient

from clients.models import HealthStatus, System, SystemType
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def test_unknown_slug_404(client_record):
    resp = DjangoClient().get("/status/never-set/")
    assert resp.status_code == 404


def test_disabled_client_404_even_when_name_matches(client_record):
    # Slug is None until Marco sets it — page must NOT exist by default.
    resp = DjangoClient().get(f"/status/{client_record.name.lower()}/")
    assert resp.status_code == 404


def test_enabled_status_page_renders_systems(client_record):
    client_record.status_page_slug = "acme-status"
    client_record.save()
    System.objects.create(
        client=client_record, name="UniFi", type=SystemType.NETWORK,
        health_status=HealthStatus.OK,
    )
    System.objects.create(
        client=client_record, name="CCTV", type=SystemType.SECURITY,
        health_status=HealthStatus.DEGRADED,
    )
    resp = DjangoClient().get("/status/acme-status/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "UniFi" in body
    assert "Operational" in body
    assert "CCTV" in body
    assert "Degraded" in body


def test_status_page_lists_recent_high_priority_tickets(client_record):
    client_record.status_page_slug = "acme-2"
    client_record.save()
    Ticket.objects.create(
        client=client_record, subject="recent CRITICAL outage",
        priority=Ticket.Priority.CRITICAL,
    )
    Ticket.objects.create(
        client=client_record, subject="low-prio question",
        priority=Ticket.Priority.LOW,
    )
    resp = DjangoClient().get("/status/acme-2/")
    body = resp.content.decode()
    assert "recent CRITICAL outage" in body
    # Low-priority shouldn't appear in the incidents list.
    assert "low-prio question" not in body
