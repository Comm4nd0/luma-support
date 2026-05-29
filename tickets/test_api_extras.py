"""Tests for the API additions: draft-reply action, maintenance CRUD."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from tickets.models import MaintenanceSchedule, Ticket, TicketTag, TicketTemplate

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


# ----- /tickets/dashboard-stats/ ---------------------------------------


def test_dashboard_stats_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        email="c@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    c = APIClient()
    c.force_authenticate(user)
    resp = c.get("/api/v1/tickets/tickets/dashboard-stats/")
    assert resp.status_code == 403


def test_dashboard_stats_returns_expected_keys(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/tickets/tickets/dashboard-stats/")
    assert resp.status_code == 200
    body = resp.json()
    assert {
        "unbilled_hours",
        "mtd_invoiced",
        "mtd_paid",
        "overdue_invoices",
        "maintenance_due_7d",
        "currency",
        "sla_digest",
    } <= set(body.keys())
    assert {"within_hours", "breached", "approaching", "total"} <= set(
        body["sla_digest"].keys()
    )


def test_dashboard_stats_sla_digest_counts_breached_and_approaching(
    engineer_user, client_record
):
    from datetime import timedelta

    from django.utils import timezone

    from tickets.models import Ticket

    now = timezone.now()
    # One already breached, one approaching within the 8h window, one safely
    # outside it (should not be counted).
    breached = Ticket.objects.create(
        client=client_record, subject="down", priority="high"
    )
    Ticket.objects.filter(pk=breached.pk).update(
        sla_deadline=now - timedelta(hours=1)
    )
    approaching = Ticket.objects.create(
        client=client_record, subject="soon", priority="high"
    )
    Ticket.objects.filter(pk=approaching.pk).update(
        sla_deadline=now + timedelta(hours=2)
    )
    far = Ticket.objects.create(
        client=client_record, subject="later", priority="low"
    )
    Ticket.objects.filter(pk=far.pk).update(
        sla_deadline=now + timedelta(hours=48)
    )

    c = APIClient()
    c.force_authenticate(engineer_user)
    digest = c.get("/api/v1/tickets/tickets/dashboard-stats/").json()["sla_digest"]
    assert digest["within_hours"] == 8
    assert digest["breached"] >= 1
    assert digest["approaching"] >= 1
    assert digest["total"] == digest["breached"] + digest["approaching"]


# ----- /tickets/<id>/merge-into/<target_id>/ ----------------------------


def test_merge_moves_notes_time_attachments_and_closes_source(engineer_user, client_record):
    from tickets.models import TicketNote, TicketTag, TimeEntry

    a = Ticket.objects.create(client=client_record, subject="A")
    b = Ticket.objects.create(client=client_record, subject="B")
    TicketNote.objects.create(ticket=a, author=engineer_user, body="from A", internal=False)
    TimeEntry.objects.create(ticket=a, user=engineer_user, minutes=10)
    tag = TicketTag.objects.create(name="UniFi", slug="unifi")
    a.tags.add(tag)

    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(f"/api/v1/tickets/tickets/{a.pk}/merge-into/{b.pk}/")
    assert resp.status_code == 200, resp.json()

    a.refresh_from_db()
    b.refresh_from_db()
    assert a.status == Ticket.Status.CLOSED
    # Original note + the system "merged" notes on both sides.
    assert b.notes.filter(body__icontains="from A").count() == 1
    assert b.notes.filter(body__icontains=f"Merged #{a.pk}").exists()
    assert a.notes.filter(body__icontains=f"Merged into #{b.pk}").exists()
    assert b.time_entries.count() == 1
    assert tag in b.tags.all()


def test_merge_refuses_cross_client(engineer_user, client_record):
    from clients.models import Client

    other = Client.objects.create(name="Other co")
    a = Ticket.objects.create(client=client_record, subject="A")
    b = Ticket.objects.create(client=other, subject="B")

    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(f"/api/v1/tickets/tickets/{a.pk}/merge-into/{b.pk}/")
    assert resp.status_code == 400


def test_merge_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="cmerge@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    a = Ticket.objects.create(client=client_record, subject="A")
    b = Ticket.objects.create(client=client_record, subject="B")
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.post(f"/api/v1/tickets/tickets/{a.pk}/merge-into/{b.pk}/")
    assert resp.status_code == 403


# ----- /tickets/<id>/summarise/ -----------------------------------------


def test_summarise_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        email="cs@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    t = Ticket.objects.create(client=client_record, subject="x")
    c = APIClient()
    c.force_authenticate(user)
    resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/summarise/")
    assert resp.status_code == 403


def test_summarise_returns_empty_when_disabled(engineer_user, client_record, settings):
    settings.ANTHROPIC_API_KEY = ""
    t = Ticket.objects.create(client=client_record, subject="x")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/summarise/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == ""
    assert body["cached"] is False


def test_summarise_uses_cache_when_present(engineer_user, client_record):
    from django.utils import timezone

    t = Ticket.objects.create(client=client_record, subject="x")
    Ticket.objects.filter(pk=t.pk).update(
        ai_summary="- already cached", ai_summary_at=timezone.now()
    )
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/summarise/")
    body = resp.json()
    assert body["summary"] == "- already cached"
    assert body["cached"] is True


def test_new_note_invalidates_summary_cache(engineer_user, client_record):
    from django.utils import timezone

    from tickets.models import TicketNote

    t = Ticket.objects.create(client=client_record, subject="x")
    Ticket.objects.filter(pk=t.pk).update(
        ai_summary="- old", ai_summary_at=timezone.now()
    )
    TicketNote.objects.create(ticket=t, author=engineer_user, body="new", internal=True)
    t.refresh_from_db()
    assert t.ai_summary == ""
    assert t.ai_summary_at is None


# ----- /tickets/bulk/ ---------------------------------------------------


def test_bulk_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        email="c2@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    t = Ticket.objects.create(client=client_record, subject="x")
    c = APIClient()
    c.force_authenticate(user)
    resp = c.post(
        "/api/v1/tickets/tickets/bulk/",
        {"ids": [t.pk], "action": "status", "value": "closed"},
        format="json",
    )
    assert resp.status_code == 403


def test_bulk_status_closes_many_tickets(engineer_user, client_record):
    tickets = [
        Ticket.objects.create(client=client_record, subject=f"t{i}") for i in range(3)
    ]
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        "/api/v1/tickets/tickets/bulk/",
        {
            "ids": [t.pk for t in tickets],
            "action": "status",
            "value": "closed",
        },
        format="json",
    )
    assert resp.status_code == 200, resp.json()
    assert resp.json() == {"touched": 3}
    for t in tickets:
        t.refresh_from_db()
        assert t.status == Ticket.Status.CLOSED


def test_bulk_add_tag_by_slug(engineer_user, client_record):
    tag = TicketTag.objects.create(name="UniFi", slug="unifi")
    tickets = [
        Ticket.objects.create(client=client_record, subject=f"t{i}") for i in range(2)
    ]
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        "/api/v1/tickets/tickets/bulk/",
        {"ids": [t.pk for t in tickets], "action": "add_tag", "value": "unifi"},
        format="json",
    )
    assert resp.status_code == 200, resp.json()
    for t in tickets:
        assert tag in t.tags.all()


def test_ticket_template_crud_is_staff_only(engineer_user, client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    client_user = User.objects.create_user(
        email="cl@acme.test",
        password="x",
        role=User.Role.CLIENT,
        client=client_record,
    )
    cuser = APIClient()
    cuser.force_authenticate(client_user)
    resp = cuser.post(
        "/api/v1/tickets/ticket-templates/",
        {"name": "T", "body": "hi", "public_default": True},
        format="json",
    )
    assert resp.status_code in (403, 404)

    eng = APIClient()
    eng.force_authenticate(engineer_user)
    resp = eng.post(
        "/api/v1/tickets/ticket-templates/",
        {"name": "Power cycle", "body": "Please reboot.", "public_default": True},
        format="json",
    )
    assert resp.status_code == 201, resp.json()
    assert TicketTemplate.objects.count() == 1
    # Client can't see them either.
    listed = cuser.get("/api/v1/tickets/ticket-templates/")
    assert listed.status_code == 200
    payload = listed.json()
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    assert rows == []


def test_bulk_writes_one_audit_row_per_ticket(engineer_user, client_record):
    from audit.models import AuditLog

    tickets = [
        Ticket.objects.create(client=client_record, subject=f"t{i}") for i in range(2)
    ]
    c = APIClient()
    c.force_authenticate(engineer_user)
    c.post(
        "/api/v1/tickets/tickets/bulk/",
        {
            "ids": [t.pk for t in tickets],
            "action": "status",
            "value": "resolved",
        },
        format="json",
    )
    rows = AuditLog.objects.filter(action="ticket.bulk.status")
    assert rows.count() == 2
