"""tickets.ai.draft_reply + the JSON draft-reply endpoint."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import Client as DjangoClient
from django.urls import reverse

from tickets.ai import draft_kb_article, draft_reply, triage_ticket
from tickets.models import Ticket, TicketNote, TicketTag

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


# ----- triage_ticket ---------------------------------------------------


def test_triage_returns_none_when_key_unset(client_record, settings):
    settings.ANTHROPIC_API_KEY = ""
    assert triage_ticket(_ticket(client_record)) is None


def test_triage_parses_claude_json(client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    TicketTag.objects.create(name="UniFi", slug="unifi")
    TicketTag.objects.create(name="Outage", slug="outage")
    payload = (
        '{"priority": "high", "tag_slugs": ["unifi", "made-up"], '
        '"reasoning": "office wifi down"}'
    )
    fake_msg = SimpleNamespace(content=[SimpleNamespace(text=payload)])
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        result = triage_ticket(_ticket(client_record))
    assert result == {
        "priority": "high",
        # Unknown slug filtered out, known slug kept.
        "tag_slugs": ["unifi"],
        "reasoning": "office wifi down",
    }


def test_triage_rejects_bad_priority(client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_msg = SimpleNamespace(
        content=[SimpleNamespace(text='{"priority": "wat", "tag_slugs": []}')]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        assert triage_ticket(_ticket(client_record)) is None


def test_triage_swallows_errors(client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    with patch("anthropic.Anthropic", side_effect=RuntimeError("api down")):
        assert triage_ticket(_ticket(client_record)) is None


def test_triage_task_applies_priority_and_tags(client_record, settings):
    from features.models import FeatureFlag
    from tickets.tasks import triage_new_ticket

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    FeatureFlag.objects.create(name="ai_triage", enabled=True, percentage=100)
    TicketTag.objects.create(name="UniFi", slug="unifi")
    t = _ticket(client_record)

    with patch(
        "tickets.ai.triage_ticket",
        return_value={
            "priority": "critical",
            "tag_slugs": ["unifi"],
            "reasoning": "wifi down across whole site",
        },
    ):
        out = triage_new_ticket(t.pk)

    assert "priority -> critical" in out
    t.refresh_from_db()
    assert t.priority == "critical"
    assert list(t.tags.values_list("slug", flat=True)) == ["unifi"]
    note = t.notes.order_by("-id").first()
    assert note is not None
    assert note.internal is True
    assert "[AI triage]" in note.body
    assert "wifi down" in note.body


def test_triage_task_no_op_when_flag_disabled(client_record, settings):
    from tickets.tasks import triage_new_ticket

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    t = _ticket(client_record)
    assert triage_new_ticket(t.pk) == "ai_triage disabled"


# ----- draft_kb_article -------------------------------------------------


def test_kb_draft_returns_none_when_key_unset(client_record, settings):
    settings.ANTHROPIC_API_KEY = ""
    assert draft_kb_article(_ticket(client_record)) is None


def test_kb_draft_parses_title_and_content(client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    payload = (
        '{"title": "Restart a UniFi AP", '
        '"content": "## Steps\\n1. Hold the reset button..."}'
    )
    fake_msg = SimpleNamespace(content=[SimpleNamespace(text=payload)])
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        result = draft_kb_article(_ticket(client_record))
    assert result == {
        "title": "Restart a UniFi AP",
        "content": "## Steps\n1. Hold the reset button...",
    }


def test_kb_draft_rejects_missing_fields(client_record, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_msg = SimpleNamespace(
        content=[SimpleNamespace(text='{"title": "", "content": "body"}')]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        assert draft_kb_article(_ticket(client_record)) is None


def test_promote_to_kb_endpoint_requires_staff(client_record, settings):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient as DrfClient

    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    User = get_user_model()
    cu = User.objects.create_user(
        email="cu@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    t = _ticket(client_record)
    c = DrfClient()
    c.force_authenticate(cu)
    resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/promote-to-kb/")
    assert resp.status_code == 403


def test_promote_to_kb_endpoint_returns_null_draft_when_disabled(
    engineer_user, client_record, settings
):
    from rest_framework.test import APIClient as DrfClient

    settings.ANTHROPIC_API_KEY = ""
    t = _ticket(client_record)
    c = DrfClient()
    c.force_authenticate(engineer_user)
    resp = c.post(f"/api/v1/tickets/tickets/{t.pk}/promote-to-kb/")
    assert resp.status_code == 200
    assert resp.json() == {"draft": None}
