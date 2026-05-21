"""Tests for the generic /api/v1/tickets/webhook/<token>/ ingest."""
import json

import pytest
from django.test import Client as DjangoClient

from tickets.models import IngestEndpoint, Ticket

pytestmark = pytest.mark.django_db


def _endpoint(client_record, **kwargs):
    return IngestEndpoint.objects.create(
        name=kwargs.pop("name", "Grafana prod"),
        token=IngestEndpoint.generate_token(),
        client=client_record,
        **kwargs,
    )


def test_unknown_token_returns_404(client_record):
    web = DjangoClient()
    resp = web.post(
        "/api/v1/tickets/webhook/nope/",
        data=json.dumps({"title": "x"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_disabled_endpoint_returns_404(client_record):
    ep = _endpoint(client_record, enabled=False)
    web = DjangoClient()
    resp = web.post(
        f"/api/v1/tickets/webhook/{ep.token}/",
        data=json.dumps({"title": "x"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_payload_creates_ticket_with_default_priority(client_record):
    ep = _endpoint(client_record, default_priority="high")
    web = DjangoClient()
    resp = web.post(
        f"/api/v1/tickets/webhook/{ep.token}/",
        data=json.dumps({"title": "Disk full on web01", "message": "/var at 95%"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    tid = resp.json()["ticket_id"]
    t = Ticket.objects.get(pk=tid)
    assert t.client_id == client_record.pk
    assert t.subject == "Disk full on web01"
    assert "/var at 95%" in t.description
    assert t.priority == "high"


def test_missing_subject_field_falls_back_to_endpoint_name(client_record):
    ep = _endpoint(client_record, name="Uptime Kuma")
    web = DjangoClient()
    resp = web.post(
        f"/api/v1/tickets/webhook/{ep.token}/",
        data=json.dumps({"message": "Just a body"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    t = Ticket.objects.get(pk=resp.json()["ticket_id"])
    assert "Uptime Kuma" in t.subject


def test_missing_body_field_uses_full_payload(client_record):
    ep = _endpoint(client_record, body_field="msg")  # not in payload
    web = DjangoClient()
    resp = web.post(
        f"/api/v1/tickets/webhook/{ep.token}/",
        data=json.dumps({"title": "x", "extra": {"a": 1}}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    t = Ticket.objects.get(pk=resp.json()["ticket_id"])
    # Fallback dumps the whole payload so signal isn't lost.
    assert '"extra"' in t.description


def test_dotted_field_path(client_record):
    ep = _endpoint(client_record, subject_field="alert.name")
    web = DjangoClient()
    resp = web.post(
        f"/api/v1/tickets/webhook/{ep.token}/",
        data=json.dumps({"alert": {"name": "CPU >90%"}}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    t = Ticket.objects.get(pk=resp.json()["ticket_id"])
    assert t.subject == "CPU >90%"


def test_bad_json_returns_400_and_stamps_status(client_record):
    ep = _endpoint(client_record)
    web = DjangoClient()
    resp = web.post(
        f"/api/v1/tickets/webhook/{ep.token}/",
        data="not json at all",
        content_type="application/json",
    )
    assert resp.status_code == 400
    ep.refresh_from_db()
    assert ep.last_status == "bad-json"
    assert ep.last_called_at is not None
