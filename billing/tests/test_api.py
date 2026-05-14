import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
def test_engineer_cannot_list_invoices(api, engineer_user):
    api.force_authenticate(engineer_user)
    resp = api.get("/api/v1/billing/invoices/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_list_invoices(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    resp = api.get("/api/v1/billing/invoices/")
    assert resp.status_code == 200
    assert resp.data["count"] == 1
    assert resp.data["results"][0]["id"] == invoice.pk


@pytest.mark.django_db
def test_admin_can_create_one_off_invoice(api, admin_user, client_record):
    api.force_authenticate(admin_user)
    payload = {
        "client": client_record.pk,
        "currency": "GBP",
        "lines": [
            {
                "description": "Onsite hour",
                "quantity": "2.00",
                "unit_amount": "60.00",
            }
        ],
    }
    resp = api.post("/api/v1/billing/invoices/", payload, format="json")
    assert resp.status_code == 201, dict(resp.data)
    assert resp.data["subtotal"] == "120.00"
    assert resp.data["total"] == "120.00"


@pytest.mark.django_db
def test_send_endpoint_requires_connection(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    resp = api.post(f"/api/v1/billing/invoices/{invoice.pk}/send/")
    assert resp.status_code == 400
    assert "not connected" in resp.data["detail"].lower()


@pytest.mark.django_db
def test_engineer_cannot_list_payments(api, engineer_user):
    api.force_authenticate(engineer_user)
    resp = api.get("/api/v1/billing/payments/")
    assert resp.status_code == 403
