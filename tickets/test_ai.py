"""tickets.ai.draft_reply + the JSON draft-reply endpoint."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import Client as DjangoClient
from django.urls import reverse

from tickets.ai import draft_reply
from tickets.models import Ticket, TicketNote

pytestmark = pytest.mark.django_db


def _ticket(client_record):
    return Ticket.objects.create(
        client=client_record,
        subject="WiFi keeps dropping",
        description="Every 30 mins for the past week.",
    )


# ----- draft_reply -----------------------------------------------------


def test_draft_reply_returns_empty_when_key_unset(client_record, settings):
    settings.ANTHROPIC_API_KEY = ""
    assert draft_reply(_ticket(client_record)) == ""


def test_draft_reply_returns_text_from_claude(client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_msg = SimpleNamespace(
        content=[SimpleNamespace(text="Hi — try a power cycle.")]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        out = draft_reply(_ticket(client_record))
    assert out == "Hi — try a power cycle."


def test_draft_reply_swallows_exceptions(client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    with patch("anthropic.Anthropic", side_effect=RuntimeError("api down")):
        assert draft_reply(_ticket(client_record)) == ""


def test_draft_reply_excludes_internal_notes(client_record, settings, engineer_user):
    """Internal engineer notes must not leak into a client-facing draft prompt."""
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    t = _ticket(client_record)
    TicketNote.objects.create(
        ticket=t, author=engineer_user, body="SECRET internal triage", internal=True
    )
    TicketNote.objects.create(
        ticket=t, author=engineer_user, body="Public update", internal=False
    )

    captured = {}

    def capture_create(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return SimpleNamespace(content=[SimpleNamespace(text="ok")])

    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=capture_create)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        draft_reply(t)

    user_content = captured["messages"][0]["content"]
    assert "SECRET internal triage" not in user_content
    assert "Public update" in user_content


# ----- view endpoint ---------------------------------------------------


def test_draft_reply_view_requires_staff(client_record, settings):
    """Client users can't ask the AI to draft engineer replies."""
    from django.contrib.auth import get_user_model

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    User = get_user_model()
    user = User.objects.create_user(
        email="c@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    t = _ticket(client_record)
    c = DjangoClient()
    c.force_login(user)
    resp = c.post(reverse("portal:ticket_draft_reply", args=[t.pk]))
    assert resp.status_code == 403


def test_draft_reply_view_returns_json(engineer_user, client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_msg = SimpleNamespace(content=[SimpleNamespace(text="suggested reply")])
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    t = _ticket(client_record)
    c = DjangoClient()
    c.force_login(engineer_user)
    with patch("anthropic.Anthropic", return_value=fake_client):
        resp = c.post(reverse("portal:ticket_draft_reply", args=[t.pk]))
    assert resp.status_code == 200
    assert resp.json() == {"draft": "suggested reply"}


def test_draft_reply_view_returns_empty_draft_when_disabled(
    engineer_user, client_record, settings
):
    settings.ANTHROPIC_API_KEY = ""
    t = _ticket(client_record)
    c = DjangoClient()
    c.force_login(engineer_user)
    resp = c.post(reverse("portal:ticket_draft_reply", args=[t.pk]))
    assert resp.status_code == 200
    assert resp.json() == {"draft": ""}
