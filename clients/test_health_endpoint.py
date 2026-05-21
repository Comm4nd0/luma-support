import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_health_endpoint_returns_breakdown(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(f"/api/v1/clients/clients/{client_record.pk}/health/")
    assert resp.status_code == 200
    body = resp.json()
    assert {"score", "band", "csat", "open_tickets",
            "overdue_invoices", "systems_ok_pct", "reasons"} <= set(body.keys())
    assert isinstance(body["score"], int)
    assert body["band"] in {"good", "watch", "at_risk"}
    assert body["client_id"] == client_record.pk


def test_health_endpoint_scoped_to_user_client(client_record):
    """Client users only see health for their own client."""
    from django.contrib.auth import get_user_model

    from clients.models import Client

    other = Client.objects.create(name="Other")
    User = get_user_model()
    cu = User.objects.create_user(
        email="ch@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    c = APIClient()
    c.force_authenticate(cu)
    own = c.get(f"/api/v1/clients/clients/{client_record.pk}/health/")
    assert own.status_code == 200
    forbidden = c.get(f"/api/v1/clients/clients/{other.pk}/health/")
    # Scoped queryset returns 404 for out-of-scope clients.
    assert forbidden.status_code == 404
