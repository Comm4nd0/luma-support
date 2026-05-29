from decimal import Decimal

import pytest

from billing.models import Invoice, InvoiceLine


@pytest.mark.django_db
def test_invoice_line_total_computed_on_save(client_record):
    inv = Invoice.objects.create(client=client_record, kind=Invoice.Kind.ONE_OFF)
    line = InvoiceLine.objects.create(
        invoice=inv,
        description="Patch panel",
        quantity=Decimal("2.00"),
        unit_amount=Decimal("12.50"),
    )
    assert line.line_total == Decimal("25.00")


@pytest.mark.django_db
def test_invoice_recalculate_totals_sums_lines(client_record):
    inv = Invoice.objects.create(client=client_record, kind=Invoice.Kind.ONE_OFF)
    InvoiceLine.objects.create(
        invoice=inv,
        description="A",
        quantity=Decimal("1"),
        unit_amount=Decimal("10.00"),
    )
    InvoiceLine.objects.create(
        invoice=inv,
        description="B",
        quantity=Decimal("3"),
        unit_amount=Decimal("5.50"),
    )
    inv.recalculate_totals()
    inv.save()
    inv.refresh_from_db()
    assert inv.subtotal == Decimal("26.50")
    assert inv.total == Decimal("26.50")


@pytest.mark.django_db
def test_xero_connection_singleton(admin_user):
    from datetime import timedelta

    from django.utils import timezone

    from billing.models import XeroConnection

    a = XeroConnection(
        tenant_id="t1",
        access_token="at",
        expires_at=timezone.now() + timedelta(hours=1),
        connected_by=admin_user,
    )
    a.set_refresh_token("rt-1")
    a.save()

    b = XeroConnection(
        tenant_id="t2",
        access_token="at2",
        expires_at=timezone.now() + timedelta(hours=1),
        connected_by=admin_user,
    )
    b.set_refresh_token("rt-2")
    b.save()

    assert XeroConnection.objects.count() == 1
    only = XeroConnection.objects.get()
    assert only.tenant_id == "t2"
    assert only.get_refresh_token() == "rt-2"
