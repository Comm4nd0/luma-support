"""Per-client KB article scoping."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from clients.models import Client
from knowledge.models import Article

pytestmark = pytest.mark.django_db


def _published(**kwargs):
    return Article.objects.create(
        title=kwargs.pop("title", "title"),
        content="x",
        published_at=timezone.now(),
        **kwargs,
    )


def _client_user(client):
    User = get_user_model()
    return User.objects.create_user(
        email=f"u{client.pk}@acme.test",
        password="x",
        role=User.Role.CLIENT,
        client=client,
    )


def test_internal_articles_hidden_from_clients(client_record):
    _published(title="internal-doc", visibility=Article.Visibility.INTERNAL)
    qs = Article.objects.for_client(client_record)
    assert qs.filter(title="internal-doc").exists() is False


def test_all_clients_visible_to_every_client(client_record):
    a = _published(title="how-to", visibility=Article.Visibility.ALL_CLIENTS)
    assert a in Article.objects.for_client(client_record)


def test_specific_clients_filters_by_membership(client_record):
    other = Client.objects.create(name="Other")
    a = _published(title="acme-only", visibility=Article.Visibility.SPECIFIC_CLIENTS)
    a.allowed_clients.add(client_record)
    assert a in Article.objects.for_client(client_record)
    assert a not in Article.objects.for_client(other)


def test_api_scoping_works_end_to_end(client_record):
    a = _published(title="acme-only", visibility=Article.Visibility.SPECIFIC_CLIENTS)
    a.allowed_clients.add(client_record)
    other_only = _published(
        title="other-only", visibility=Article.Visibility.SPECIFIC_CLIENTS
    )
    other = Client.objects.create(name="Other co")
    other_only.allowed_clients.add(other)
    cu = _client_user(client_record)
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.get("/api/v1/knowledge/articles/")
    body = resp.json()
    rows = body["results"] if isinstance(body, dict) and "results" in body else body
    titles = {a["title"] for a in rows}
    assert "acme-only" in titles
    assert "other-only" not in titles


def test_client_visible_backwards_compat_synced_on_save():
    a = Article.objects.create(
        title="x", content="x", visibility=Article.Visibility.ALL_CLIENTS
    )
    # Saving an ALL_CLIENTS article flips legacy client_visible to True.
    assert a.client_visible is True
    a.visibility = Article.Visibility.INTERNAL
    a.save()
    a.refresh_from_db()
    assert a.client_visible is False
