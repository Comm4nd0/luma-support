"""Portal 'Clear queue' page — parity with the mobile InboxZeroScreen."""
import pytest
from django.test import Client as DjangoClient

from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def test_clear_queue_redirects_non_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="cq@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    c = DjangoClient()
    c.force_login(cu)
    resp = c.get("/tickets/clear-queue/")
    assert resp.status_code == 302  # StaffRequiredMixin bounces to dashboard


def test_clear_queue_lists_ai_suggestions(engineer_user, client_record, settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    mine = Ticket.objects.create(
        client=client_record, subject="needs reply", assigned_to=engineer_user
    )
    monkeypatch.setattr(
        "tickets.ai.propose_inbox_actions",
        lambda tickets: [
            {"ticket_id": mine.pk, "action": "reply", "reason": "client is waiting"}
        ],
    )
    c = DjangoClient()
    c.force_login(engineer_user)
    resp = c.get("/tickets/clear-queue/")
    assert resp.status_code == 200
    rows = resp.context["rows"]
    assert len(rows) == 1
    assert rows[0]["ticket"].pk == mine.pk
    assert rows[0]["action"] == "reply"


def test_clear_queue_close_action_closes_ticket(engineer_user, client_record):
    t = Ticket.objects.create(
        client=client_record, subject="done", assigned_to=engineer_user
    )
    c = DjangoClient()
    c.force_login(engineer_user)
    resp = c.post("/tickets/clear-queue/", {"ticket_id": t.pk})
    assert resp.status_code == 302
    t.refresh_from_db()
    assert t.status == Ticket.Status.CLOSED


def test_clear_queue_close_ignores_unknown_ticket(engineer_user):
    c = DjangoClient()
    c.force_login(engineer_user)
    resp = c.post("/tickets/clear-queue/", {"ticket_id": 999999})
    assert resp.status_code == 302  # gracefully redirects, no crash
