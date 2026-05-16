"""knowledge.ai: keyword fallback + Claude path (mocked) + ticket-create flow."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.urls import reverse
from django.utils import timezone

from knowledge.ai import Suggestion, suggest_articles
from knowledge.models import Article

pytestmark = pytest.mark.django_db


@pytest.fixture
def kb(db):
    now = timezone.now()
    return [
        Article.objects.create(
            title="Resetting your WiFi router",
            content="Power cycle the router and wait for the green light.",
            client_visible=True,
            published_at=now,
        ),
        Article.objects.create(
            title="Replacing a CCTV camera",
            content="Disconnect PoE and remove the mounting screws.",
            client_visible=True,
            published_at=now,
        ),
        Article.objects.create(
            title="Configuring Home Assistant scenes",
            content="Open the YAML editor and define a scene.",
            client_visible=False,  # engineer-only
            published_at=now,
        ),
    ]


# ----- keyword fallback ------------------------------------------------


def test_keyword_suggest_picks_relevant(kb, settings):
    settings.ANTHROPIC_API_KEY = ""  # force fallback
    out = suggest_articles("My wifi is broken", "I tried resetting the router.")
    assert out
    titles = [s.article.title for s in out]
    assert "Resetting your WiFi router" in titles


def test_keyword_suggest_empty_input_returns_empty(kb, settings):
    settings.ANTHROPIC_API_KEY = ""
    assert suggest_articles("", "") == []


def test_keyword_suggest_no_match_returns_empty(kb, settings):
    settings.ANTHROPIC_API_KEY = ""
    assert suggest_articles("unrelated topic", "nothing to see") == []


def test_keyword_suggest_filters_to_client_visible(kb, settings):
    settings.ANTHROPIC_API_KEY = ""
    out = suggest_articles(
        "scene configuration in home automation",
        "",
        client_visible_only=True,
    )
    # The Home Assistant article is staff-only.
    assert all(s.article.client_visible for s in out)


# ----- Claude path -----------------------------------------------------


def test_claude_suggest_happy_path(kb, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_msg = SimpleNamespace(
        content=[
            SimpleNamespace(
                text='{"suggestions":[{"slug":"resetting-your-wifi-router","reason":"router reset"}]}'
            )
        ]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        out = suggest_articles("WiFi help", "everything stopped")
    assert len(out) == 1
    assert out[0].article.slug == "resetting-your-wifi-router"
    assert out[0].reason == "router reset"


def test_claude_failure_falls_back_to_keyword(kb, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"

    def boom(*_a, **_kw):
        raise RuntimeError("API down")

    with patch("anthropic.Anthropic", side_effect=boom):
        out = suggest_articles("wifi reset", "")
    # Fallback kicks in — still gets a hit.
    assert any("WiFi" in s.article.title for s in out)


def test_claude_returns_unknown_slug_is_dropped(kb, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_msg = SimpleNamespace(
        content=[
            SimpleNamespace(
                text='{"suggestions":[{"slug":"nope","reason":"x"},{"slug":"replacing-a-cctv-camera","reason":"y"}]}'
            )
        ]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        out = suggest_articles("camera replacement", "")
    assert [s.article.slug for s in out] == ["replacing-a-cctv-camera"]


def test_claude_non_json_returns_empty(kb, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    fake_msg = SimpleNamespace(
        content=[SimpleNamespace(text="not json at all")]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg)
    )
    with patch("anthropic.Anthropic", return_value=fake_client):
        out = suggest_articles("anything", "")
    assert out == []


# ----- ticket-create UI hook -------------------------------------------


def test_ticket_create_suggest_action_renders_suggestions(
    engineer_user, client_record, kb, settings
):
    settings.ANTHROPIC_API_KEY = ""  # keyword fallback path
    client = DjangoClient()
    client.force_login(engineer_user)

    resp = client.post(
        reverse("portal:ticket_create"),
        {
            "client": str(client_record.pk),
            "subject": "wifi router reset",
            "description": "tried power cycle",
            "priority": "",
            "_action": "suggest",
        },
    )
    # Form re-renders, no new ticket created.
    assert resp.status_code == 200
    assert b"Resetting your WiFi router" in resp.content
    from tickets.models import Ticket

    assert Ticket.objects.count() == 0


def test_ticket_create_submit_action_still_creates(engineer_user, client_record, kb):
    client = DjangoClient()
    client.force_login(engineer_user)
    resp = client.post(
        reverse("portal:ticket_create"),
        {
            "client": str(client_record.pk),
            "subject": "wifi reset",
            "description": "tried it",
            "priority": "low",
            "_action": "submit",
        },
    )
    assert resp.status_code == 302
    from tickets.models import Ticket

    assert Ticket.objects.filter(subject="wifi reset").exists()
