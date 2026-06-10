"""Upload validation on ticket attachments (size + extension allowlist)."""
from io import BytesIO

import pytest
from rest_framework.test import APIClient

from tickets.models import Attachment, Ticket

pytestmark = pytest.mark.django_db


def _file(name, payload=b"hello"):
    f = BytesIO(payload)
    f.name = name
    return f


@pytest.fixture
def ticket(client_record):
    return Ticket.objects.create(
        client=client_record, subject="s", description="d"
    )


def _upload(user, ticket, f):
    c = APIClient()
    c.force_authenticate(user)
    return c.post(
        f"/api/v1/tickets/tickets/{ticket.pk}/attachments/",
        {"file": f},
        format="multipart",
    )


def test_allowed_extension_accepted(engineer_user, ticket):
    resp = _upload(engineer_user, ticket, _file("photo.png"))
    assert resp.status_code == 201, resp.json()
    assert Attachment.objects.filter(ticket=ticket).count() == 1


def test_disallowed_extension_rejected(engineer_user, ticket):
    resp = _upload(engineer_user, ticket, _file("payload.exe"))
    assert resp.status_code == 400
    assert "not allowed" in str(resp.json())
    assert Attachment.objects.count() == 0


def test_extensionless_file_rejected(engineer_user, ticket):
    resp = _upload(engineer_user, ticket, _file("README"))
    assert resp.status_code == 400
    assert Attachment.objects.count() == 0


def test_oversized_file_rejected(engineer_user, ticket, settings):
    settings.MAX_UPLOAD_BYTES = 10
    resp = _upload(engineer_user, ticket, _file("big.png", b"x" * 11))
    assert resp.status_code == 400
    assert "too large" in str(resp.json())
    assert Attachment.objects.count() == 0
