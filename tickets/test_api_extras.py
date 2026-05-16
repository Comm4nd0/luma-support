"""Tests for the API additions: draft-reply action, maintenance CRUD."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from tickets.models import MaintenanceSchedule, Ticket

pytestmark = pytest.mark.django_db


# ----- /tickets/<id>/draft-reply/ ---------------------------------------


def test_draft_reply_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        email="c@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    t = Ticket.objects.create(client=client_record, subject="x")
    c = APIClient()
    c.force_authenticate(user)
    resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/draft-reply/")
    assert resp.status_code == 403


def test_draft_reply_returns_empty_when_disabled(engineer_user, client_record, settings):
    settings.ANTHROPIC_API_KEY = ""
    t = Ticket.objects.create(client=client_record, subject="x")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/draft-reply/")
    assert resp.status_code == 200
    assert resp.json() == {"draft": ""}


def test_draft_reply_returns_text_when_enabled(engineer_user, client_record, settings):
    from types import SimpleNamespace

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    t = Ticket.objects.create(client=client_record, subject="x")
    fake_msg = SimpleNamespace(content=[SimpleNamespace(text="Hi from Claude")])
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    c = APIClient()
    c.force_authenticate(engineer_user)
    with patch("anthropic.Anthropic", return_value=fake_client):
        resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/draft-reply/")
    assert resp.status_code == 200
    assert resp.json()["draft"] == "Hi from Claude"


# ----- /maintenance-schedules/ -----------------------------------------


def test_maintenance_create_staff_only(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    client_user = User.objects.create_user(
        email="alice@acme.test",
        password="x",
        role=User.Role.CLIENT,
        client=client_record,
    )
    c = APIClient()
    c.force_authenticate(client_user)
    resp = c.get("/api/v1/tickets/maintenance-schedules/")
    # Empty queryset for client users.
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_maintenance_create_and_list_for_engineer(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        "/api/v1/tickets/maintenance-schedules/",
        {
            "client": client_record.pk,
            "cadence": "monthly",
            "next_run_at": str(date.today()),
            "template_subject": "Monthly check",
            "template_description": "",
            "priority": "",
            "active": True,
        },
        format="json",
    )
    assert resp.status_code == 201
    sched = MaintenanceSchedule.objects.get()
    assert sched.template_subject == "Monthly check"

    resp = c.get("/api/v1/tickets/maintenance-schedules/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
