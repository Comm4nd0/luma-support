"""Per-client document library."""
from io import BytesIO

import pytest
from rest_framework.test import APIClient

from clients.models import Client, ClientDocument

pytestmark = pytest.mark.django_db


def _pdf(name="welcome.pdf"):
    f = BytesIO(b"%PDF-1.4\n%fake pdf body\n")
    f.name = name
    return f


def _client_user(client):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        email=f"cd{client.pk}@acme.test", password="x",
        role=get_user_model().Role.CLIENT, client=client,
    )


def test_client_user_cannot_upload(client_record):
    cu = _client_user(client_record)
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.post(
        "/api/v1/clients/documents/",
        {"client": client_record.pk, "title": "x", "file": _pdf()},
        format="multipart",
    )
    assert resp.status_code == 403


def test_engineer_upload_stamps_uploader(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        "/api/v1/clients/documents/",
        {
            "client": client_record.pk,
            "title": "Welcome pack",
            "kind": "welcome",
            "file": _pdf(),
        },
        format="multipart",
    )
    assert resp.status_code == 201, resp.json()
    doc = ClientDocument.objects.get()
    assert doc.uploaded_by == engineer_user


def test_client_user_only_sees_own_visible_docs(client_record):
    other = Client.objects.create(name="Other")
    visible = ClientDocument.objects.create(
        client=client_record, title="mine-visible", file="x.pdf",
        client_visible=True,
    )
    ClientDocument.objects.create(
        client=client_record, title="mine-hidden", file="x.pdf",
        client_visible=False,
    )
    ClientDocument.objects.create(
        client=other, title="theirs", file="x.pdf", client_visible=True,
    )
    cu = _client_user(client_record)
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.get("/api/v1/clients/documents/")
    body = resp.json()
    rows = body["results"] if isinstance(body, dict) and "results" in body else body
    titles = {r["title"] for r in rows}
    assert titles == {"mine-visible"}
    assert visible.client_visible is True
