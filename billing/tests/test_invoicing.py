from datetime import date
from decimal import Decimal

import pytest

from billing.models import Invoice
from billing.services import generate_contract_invoice, generate_time_invoice
from clients.models import CarePlanTier, Client
from tickets.models import Ticket, TimeEntry


@pytest.fixture
def billed_client(db):
    return Client.objects.create(
        name="Acme",
        care_plan_tier=CarePlanTier.PROFESSIONAL,
        monthly_fee=Decimal("99.00"),
        hourly_rate=Decimal("80.00"),
    )


@pytest.mark.django_db
def test_generate_contract_invoice_creates_one_line(billed_client):
    invoice, was_new = generate_contract_invoice(billed_client, date(2026, 5, 14))
    assert was_new is True
    assert invoice.kind == Invoice.Kind.CONTRACT
    assert invoice.status == Invoice.Status.DRAFT
    assert invoice.period_start == date(2026, 5, 1)
    assert invoice.period_end == date(2026, 5, 31)
    assert invoice.lines.count() == 1
    assert invoice.subtotal == Decimal("99.00")


@pytest.mark.django_db
def test_generate_contract_invoice_is_idempotent(billed_client):
    a, new_a = generate_contract_invoice(billed_client, date(2026, 5, 14))
    b, new_b = generate_contract_invoice(billed_client, date(2026, 5, 28))
    assert new_a is True
    assert new_b is False
    assert a.pk == b.pk
    assert Invoice.objects.filter(client=billed_client, kind="contract").count() == 1


@pytest.mark.django_db
def test_generate_contract_invoice_skips_tier_none():
    c = Client.objects.create(
        name="Adhoc", care_plan_tier=CarePlanTier.NONE, monthly_fee=Decimal("0")
    )
    inv, new = generate_contract_invoice(c, date(2026, 5, 14))
    assert inv is None
    assert new is False


@pytest.mark.django_db
def test_generate_contract_invoice_skips_zero_fee():
    c = Client.objects.create(
        name="Free", care_plan_tier=CarePlanTier.ESSENTIAL, monthly_fee=None
    )
    inv, new = generate_contract_invoice(c, date(2026, 5, 14))
    assert inv is None
    assert new is False


@pytest.mark.django_db
def test_generate_time_invoice_groups_by_ticket(billed_client, admin_user):
    t1 = Ticket.objects.create(client=billed_client, subject="Patch UniFi")
    t2 = Ticket.objects.create(client=billed_client, subject="Replace switch")
    TimeEntry.objects.create(ticket=t1, user=admin_user, minutes=30)
    TimeEntry.objects.create(ticket=t1, user=admin_user, minutes=45)
    TimeEntry.objects.create(ticket=t2, user=admin_user, minutes=60)

    inv = generate_time_invoice(billed_client)
    assert inv is not None
    assert inv.kind == Invoice.Kind.TIME
    assert inv.lines.count() == 2

    by_desc = {line.description: line for line in inv.lines.all()}
    t1_line = by_desc[f"#{t1.pk} {t1.subject}"]
    assert t1_line.quantity == Decimal("1.25")  # 30 + 45 = 75 min
    assert t1_line.unit_amount == Decimal("80.00")
    assert t1_line.line_total == Decimal("100.00")

    # All entries should be attached to a line now.
    assert TimeEntry.objects.filter(invoice_line__isnull=True).count() == 0


@pytest.mark.django_db
def test_generate_time_invoice_skips_already_billed(billed_client, admin_user):
    t = Ticket.objects.create(client=billed_client, subject="x")
    TimeEntry.objects.create(ticket=t, user=admin_user, minutes=60)
    inv1 = generate_time_invoice(billed_client)
    assert inv1 is not None

    # Second call with no new unbilled entries returns None.
    inv2 = generate_time_invoice(billed_client)
    assert inv2 is None


@pytest.mark.django_db
def test_generate_time_invoice_returns_none_when_nothing_unbilled(billed_client):
    assert generate_time_invoice(billed_client) is None


@pytest.mark.django_db
def test_contract_invoice_task_counts_only_new(billed_client):
    from billing.tasks import generate_contract_invoices

    msg1 = generate_contract_invoices()
    msg2 = generate_contract_invoices()
    assert "1 created" in msg1
    assert "0 created" in msg2
