"""Tests for the overdue-invoice dunning beat task."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from notifications.models import Notification

from .models import Invoice
from .tasks import chase_overdue_invoices, _dunning_bucket


# -----------------------------------------------------------------
# Bucket maths
# -----------------------------------------------------------------


def test_dunning_buckets():
    assert _dunning_bucket(2) is None
    assert _dunning_bucket(3) == "3"
    assert _dunning_bucket(7) == "7"
    assert _dunning_bucket(14) == "14"
    assert _dunning_bucket(15) is None
    assert _dunning_bucket(21) == "21"
    assert _dunning_bucket(28) == "28"


# -----------------------------------------------------------------
# End-to-end
# -----------------------------------------------------------------


@pytest.fixture
def overdue_invoice(client_record):
    client_record.email = "billing@client.test"
    client_record.save()
    return Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.AUTHORISED,
        subtotal=Decimal("100"),
        total=Decimal("100"),
        due_date=timezone.localdate() - timedelta(days=7),
    )


@pytest.mark.django_db
def test_chase_emails_at_bucket_match(overdue_invoice, engineer_user):
    chase_overdue_invoices()
    assert any(
        f"#{overdue_invoice.pk}" in m.subject for m in mail.outbox
    )
    assert (
        Notification.objects.filter(
            type=Notification.Type.INVOICE_OVERDUE
        ).count()
        >= 1
    )


@pytest.mark.django_db
def test_chase_dedupes_within_bucket(overdue_invoice, engineer_user):
    chase_overdue_invoices()
    chase_overdue_invoices()
    # Second run should not re-email the same bucket.
    assert (
        Notification.objects.filter(
            type=Notification.Type.INVOICE_OVERDUE
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_paid_invoices_are_left_alone(client_record):
    Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.PAID,
        subtotal=Decimal("100"),
        total=Decimal("100"),
        due_date=timezone.localdate() - timedelta(days=7),
    )
    chase_overdue_invoices()
    assert mail.outbox == []
    assert (
        Notification.objects.filter(
            type=Notification.Type.INVOICE_OVERDUE
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_invoice_within_due_date_not_chased(client_record):
    Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.AUTHORISED,
        subtotal=Decimal("100"),
        total=Decimal("100"),
        due_date=timezone.localdate() + timedelta(days=3),
    )
    chase_overdue_invoices()
    assert mail.outbox == []


# -----------------------------------------------------------------
# Dunning timeline helper + serializer
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_dunning_events_for_returns_audit_rows(client_record):
    from .dunning import dunning_events_for
    from audit import log as audit_log

    inv = Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.AUTHORISED,
        subtotal=Decimal("100"),
        total=Decimal("100"),
        due_date=timezone.localdate() - timedelta(days=8),
    )
    audit_log("invoice.dunning", target=inv, bucket="3", days_overdue=3, emailed=True)
    audit_log("invoice.dunning", target=inv, bucket="7", days_overdue=7, emailed=False)
    rows = list(dunning_events_for(inv))
    assert len(rows) == 2
    # Ordered newest-first.
    assert rows[0].metadata["bucket"] == "7"
    assert rows[1].metadata["bucket"] == "3"


@pytest.mark.django_db
def test_invoice_serializer_exposes_dunning_events(admin_user, client_record):
    from rest_framework.test import APIClient

    from audit import log as audit_log

    inv = Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.AUTHORISED,
        subtotal=Decimal("100"),
        total=Decimal("100"),
        due_date=timezone.localdate() - timedelta(days=4),
    )
    audit_log("invoice.dunning", target=inv, bucket="3", days_overdue=3, emailed=True)
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.get(f"/api/v1/billing/invoices/{inv.pk}/")
    assert resp.status_code == 200
    events = resp.json().get("dunning_events", [])
    assert len(events) == 1
    assert events[0]["bucket"] == "3"
    assert events[0]["days_overdue"] == 3
    assert events[0]["emailed"] is True
