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


@pytest.mark.django_db
def test_patch_updates_nested_lines(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    existing_line = invoice.lines.first()
    payload = {
        "notes": "Re-issued after scope change",
        "lines": [
            # update by id
            {
                "id": existing_line.pk,
                "description": "Onsite visit (revised)",
                "quantity": "2.00",
                "unit_amount": "100.00",
            },
            # create new line
            {
                "description": "Travel surcharge",
                "quantity": "1.00",
                "unit_amount": "25.00",
            },
        ],
    }
    resp = api.patch(
        f"/api/v1/billing/invoices/{invoice.pk}/", payload, format="json"
    )
    assert resp.status_code == 200, dict(resp.data)
    assert resp.data["notes"] == "Re-issued after scope change"
    assert len(resp.data["lines"]) == 2
    # 2 × 100 + 1 × 25 = 225
    assert resp.data["subtotal"] == "225.00"
    assert resp.data["total"] == "225.00"


@pytest.mark.django_db
def test_patch_omitting_a_line_id_deletes_it(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    payload = {
        "lines": [
            # only a new line — the existing one (no matching id) is dropped
            {
                "description": "Replacement",
                "quantity": "1.00",
                "unit_amount": "50.00",
            },
        ],
    }
    resp = api.patch(
        f"/api/v1/billing/invoices/{invoice.pk}/", payload, format="json"
    )
    assert resp.status_code == 200
    assert len(resp.data["lines"]) == 1
    assert resp.data["lines"][0]["description"] == "Replacement"
    assert resp.data["total"] == "50.00"


@pytest.mark.django_db
def test_patch_blocked_on_non_draft(api, admin_user, invoice):
    from billing.models import Invoice

    invoice.status = Invoice.Status.SENT
    invoice.save(update_fields=["status"])
    api.force_authenticate(admin_user)
    resp = api.patch(
        f"/api/v1/billing/invoices/{invoice.pk}/",
        {"notes": "nope"},
        format="json",
    )
    assert resp.status_code == 400
    assert "draft" in resp.data["detail"].lower()


@pytest.mark.django_db
def test_delete_blocked_on_non_draft(api, admin_user, invoice):
    from billing.models import Invoice

    invoice.status = Invoice.Status.SENT
    invoice.save(update_fields=["status"])
    api.force_authenticate(admin_user)
    resp = api.delete(f"/api/v1/billing/invoices/{invoice.pk}/")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_delete_draft(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    resp = api.delete(f"/api/v1/billing/invoices/{invoice.pk}/")
    assert resp.status_code == 204


@pytest.mark.django_db
def test_status_action_draft_to_sent(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    resp = api.post(
        f"/api/v1/billing/invoices/{invoice.pk}/status/",
        {"status": "sent"},
        format="json",
    )
    assert resp.status_code == 200, dict(resp.data)
    assert resp.data["status"] == "sent"
    assert resp.data["sent_at"] is not None


@pytest.mark.django_db
def test_status_action_rejects_illegal_transition(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    # draft → paid is not permitted by the API (Xero owns that transition).
    resp = api.post(
        f"/api/v1/billing/invoices/{invoice.pk}/status/",
        {"status": "paid"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_status_action_rejects_unknown_status(api, admin_user, invoice):
    api.force_authenticate(admin_user)
    resp = api.post(
        f"/api/v1/billing/invoices/{invoice.pk}/status/",
        {"status": "frobnicated"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_generate_from_time_creates_time_invoice(
    api, admin_user, client_record
):
    from decimal import Decimal

    from tickets.models import Ticket, TimeEntry

    ticket = Ticket.objects.create(
        client=client_record,
        subject="Wi-Fi",
        description="",
        priority="medium",
    )
    TimeEntry.objects.create(
        ticket=ticket,
        minutes=90,
        billable=True,
        user=admin_user,
    )
    api.force_authenticate(admin_user)
    resp = api.post(
        "/api/v1/billing/invoices/generate-from-time/",
        {"client": client_record.pk},
        format="json",
    )
    assert resp.status_code == 201, dict(resp.data)
    assert resp.data["kind"] == "time"
    assert len(resp.data["lines"]) == 1
    # 90 min = 1.5 h × hourly rate (the default care plan rate)
    assert Decimal(resp.data["lines"][0]["quantity"]) == Decimal("1.50")


@pytest.mark.django_db
def test_generate_from_time_no_entries(api, admin_user, client_record):
    api.force_authenticate(admin_user)
    resp = api.post(
        "/api/v1/billing/invoices/generate-from-time/",
        {"client": client_record.pk},
        format="json",
    )
    assert resp.status_code == 400
    assert "no unbilled" in resp.data["detail"].lower()
