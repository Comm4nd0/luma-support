"""/api/v1/knowledge/articles/suggest/ — JSON endpoint for KB suggestions."""
from __future__ import annotations

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from knowledge.models import Article

pytestmark = pytest.mark.django_db


@pytest.fixture
def articles(db):
    now = timezone.now()
    return [
        Article.objects.create(
            title="Resetting your WiFi router",
            content="Power-cycle the router and wait for the green light.",
            client_visible=True,
            published_at=now,
        ),
        Article.objects.create(
            title="Engineer-only HA YAML notes",
            content="Internal automation tricks.",
            client_visible=False,
            published_at=now,
        ),
    ]


def test_suggest_returns_matching_article_for_engineer(engineer_user, articles, settings):
    settings.ANTHROPIC_API_KEY = ""  # keyword fallback for determinism
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        "/api/v1/knowledge/articles/suggest/",
        {"subject": "wifi router reset", "description": ""},
        format="json",
    )
    assert resp.status_code == 200
    slugs = {s["slug"] for s in resp.json()["suggestions"]}
    assert "resetting-your-wifi-router" in slugs


def test_suggest_scopes_to_client_visible_for_client(client_record, articles, settings):
    from django.contrib.auth import get_user_model

    settings.ANTHROPIC_API_KEY = ""
    User = get_user_model()
    user = User.objects.create_user(
        email="alice@acme.test",
        password="x",
        role=User.Role.CLIENT,
        client=client_record,
    )
    c = APIClient()
    c.force_authenticate(user)
    resp = c.post(
        "/api/v1/knowledge/articles/suggest/",
        {"subject": "YAML automation tricks", "description": "anything"},
        format="json",
    )
    assert resp.status_code == 200
    # The engineer-only article must not appear.
    slugs = {s["slug"] for s in resp.json()["suggestions"]}
    assert "engineer-only-ha-yaml-notes" not in slugs


def test_suggest_requires_authentication():
    resp = APIClient().post("/api/v1/knowledge/articles/suggest/", {})
    assert resp.status_code == 401
