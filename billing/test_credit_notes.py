"""CreditNote model + /api/v1/billing/credit-notes/ endpoints."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from .models import CreditNote, Invoice

pytestmark = pytest.mark.django_db


def test_engineer_cannot_create_credit_note(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        "/api/v1/billing/credit-notes/",
        {"client": client_record.pk, "amount": "10.00"},
        format="json",
    )
    # Endpoint requires IsAdmin (not just authenticated).
    assert resp.status_code == 403


def test_admin_creates_credit_note(admin_user, client_record):
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.post(
        "/api/v1/billing/credit-notes/",
        {
            "client": client_record.pk,
            "amount": "50.00",
            "reason": "Refund for overcharge",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.json()
    cn = CreditNote.objects.get()
    assert cn.amount == Decimal("50.00")
    assert cn.status == CreditNote.Status.DRAFT
    assert cn.created_by == admin_user


def test_issue_action_marks_credit_note_issued(admin_user, client_record):
    cn = CreditNote.objects.create(client=client_record, amount=Decimal("25"))
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.post(f"/api/v1/billing/credit-notes/{cn.pk}/issue/")
    assert resp.status_code == 200
    cn.refresh_from_db()
    assert cn.status == CreditNote.Status.ISSUED
    assert cn.issued_at is not None


def test_already_issued_credit_note_cannot_be_re_issued(admin_user, client_record):
    cn = CreditNote.objects.create(
        client=client_record, amount=Decimal("25"), status=CreditNote.Status.ISSUED
    )
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.post(f"/api/v1/billing/credit-notes/{cn.pk}/issue/")
    assert resp.status_code == 400


def test_credit_note_can_link_to_invoice(admin_user, client_record):
    inv = Invoice.objects.create(
        client=client_record, kind=Invoice.Kind.ONE_OFF,
        subtotal=Decimal("100"), total=Decimal("100"),
    )
    cn = CreditNote.objects.create(
        client=client_record, invoice=inv, amount=Decimal("10")
    )
    assert cn in inv.credit_notes.all()
