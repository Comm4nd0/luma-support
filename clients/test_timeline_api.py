"""Client timeline + monthly-report API actions (mobile parity)."""
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_timeline_returns_events(engineer_user, client_record):
    from tickets.models import Ticket

    Ticket.objects.create(client=client_record, subject="Wi-Fi down", priority="high")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(f"/api/v1/clients/clients/{client_record.pk}/timeline/")
    assert resp.status_code == 200
    events = resp.json()
    assert isinstance(events, list)
    assert any(e["kind"] == "ticket" for e in events)
    # newest-first ordering + expected event shape
    assert {"kind", "occurred_at", "title", "body", "url", "pill"} <= set(
        events[0].keys()
    )


def test_timeline_is_staff_only(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="tl@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.get(f"/api/v1/clients/clients/{client_record.pk}/timeline/")
    assert resp.status_code == 403


def test_monthly_report_streams_pdf(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(
        f"/api/v1/clients/clients/{client_record.pk}/monthly-report/"
        "?year=2026&month=5"
    )
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_monthly_report_rejects_bad_month(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get(
        f"/api/v1/clients/clients/{client_record.pk}/monthly-report/?month=13"
    )
    assert resp.status_code == 400


def test_monthly_report_is_staff_only(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="mr@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.get(f"/api/v1/clients/clients/{client_record.pk}/monthly-report/")
    assert resp.status_code == 403
