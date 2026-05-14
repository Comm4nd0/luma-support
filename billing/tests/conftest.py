from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from billing.models import Invoice, InvoiceLine, XeroConnection


@pytest.fixture
def xero_connection(db, admin_user):
    conn = XeroConnection(
        tenant_id="tenant-test",
        access_token="at-test",
        expires_at=timezone.now() + timedelta(hours=1),
        connected_by=admin_user,
    )
    conn.set_refresh_token("rt-initial")
    conn.save()
    return conn


@pytest.fixture
def invoice(db, client_record):
    inv = Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        currency="GBP",
    )
    InvoiceLine.objects.create(
        invoice=inv,
        description="Onsite visit",
        quantity=Decimal("1.00"),
        unit_amount=Decimal("100.00"),
    )
    inv.recalculate_totals()
    inv.save()
    return inv
