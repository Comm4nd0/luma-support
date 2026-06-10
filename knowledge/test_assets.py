"""KB article asset uploads."""
from io import BytesIO

import pytest
from rest_framework.test import APIClient

from knowledge.models import Article, ArticleAsset

pytestmark = pytest.mark.django_db


def _png(name="test.png"):
    # 1x1 transparent PNG.
    raw = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfa\xcf"
        b"\xc0\x00\x00\x00\x03\x00\x01\xc2\xb9\x18u\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    f = BytesIO(raw)
    f.name = name
    return f


def test_engineer_can_upload_asset(engineer_user):
    a = Article.objects.create(title="t", content="x", slug="t")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        f"/api/v1/knowledge/articles/{a.slug}/assets/",
        {"file": _png("hello.png")},
        format="multipart",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["url"].endswith(".png")
    assert ArticleAsset.objects.filter(article=a).count() == 1


def test_client_user_rejected_403(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="ca@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    a = Article.objects.create(
        title="t", content="x", slug="t",
        visibility=Article.Visibility.ALL_CLIENTS,
    )
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.post(
        f"/api/v1/knowledge/articles/{a.slug}/assets/",
        {"file": _png()},
        format="multipart",
    )
    assert resp.status_code == 403


def test_missing_file_returns_400(engineer_user):
    a = Article.objects.create(title="t", content="x", slug="t")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(f"/api/v1/knowledge/articles/{a.slug}/assets/", {})
    assert resp.status_code == 400


def test_disallowed_extension_rejected(engineer_user):
    a = Article.objects.create(title="t", content="x", slug="t")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        f"/api/v1/knowledge/articles/{a.slug}/assets/",
        {"file": _png("script.exe")},
        format="multipart",
    )
    assert resp.status_code == 400
    assert ArticleAsset.objects.count() == 0


def test_oversized_asset_rejected(engineer_user, settings):
    settings.MAX_UPLOAD_BYTES = 10
    a = Article.objects.create(title="t", content="x", slug="t")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        f"/api/v1/knowledge/articles/{a.slug}/assets/",
        {"file": _png("big.png")},
        format="multipart",
    )
    assert resp.status_code == 400
    assert ArticleAsset.objects.count() == 0
