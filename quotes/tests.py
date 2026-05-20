from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from billing.models import Invoice
from leads.models import ActivityKind, Lead, LeadActivity, LeadStage

from .models import Quote, QuoteLine, QuoteStatus, _next_quote_number
from .services import accept_quote, reject_quote, send_quote


# -----------------------------------------------------------------
# Numbering / totals
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_quote_number_is_assigned_on_save(client_record):
    q = Quote.objects.create(client=client_record)
    year = timezone.localdate().year
    assert q.number.startswith(f"Q-{year}-")
    assert q.number.endswith("0001")


@pytest.mark.django_db
def test_quote_number_increments(client_record):
    Quote.objects.create(client=client_record)
    Quote.objects.create(client=client_record)
    q3 = Quote.objects.create(client=client_record)
    assert q3.number.endswith("0003")


@pytest.mark.django_db
def test_quote_lines_drive_totals(client_record):
    q = Quote.objects.create(client=client_record, tax=Decimal("10.00"))
    QuoteLine.objects.create(
        quote=q, description="UniFi Switch", quantity=2, unit_amount=Decimal("125.00")
    )
    QuoteLine.objects.create(
        quote=q, description="Install", quantity=4, unit_amount=Decimal("75.00")
    )
    q.recalculate_totals()
    assert q.subtotal == Decimal("550.00")
    assert q.total == Decimal("560.00")


@pytest.mark.django_db
def test_is_expired_only_for_open_statuses(client_record):
    yesterday = timezone.localdate() - timedelta(days=1)
    q = Quote.objects.create(
        client=client_record, valid_until=yesterday, status=QuoteStatus.SENT
    )
    assert q.is_expired
    q.status = QuoteStatus.ACCEPTED
    assert not q.is_expired


# -----------------------------------------------------------------
# Workflow: send / accept / reject
# -----------------------------------------------------------------


@pytest.fixture
def lead_with_quote(engineer_user):
    lead = Lead.objects.create(
        name="Quincy",
        email="quincy@example.com",
        stage=LeadStage.QUALIFIED,
    )
    q = Quote.objects.create(lead=lead, created_by=engineer_user)
    QuoteLine.objects.create(
        quote=q,
        description="Smart home install",
        quantity=1,
        unit_amount=Decimal("1200.00"),
    )
    q.recalculate_totals()
    q.save(update_fields=["subtotal", "total"])
    return lead, q


@pytest.mark.django_db
def test_send_quote_emails_recipient_and_logs_activity(lead_with_quote, engineer_user):
    lead, q = lead_with_quote
    sent = send_quote(q, by_user=engineer_user)
    q.refresh_from_db()
    assert sent is True
    assert q.status == QuoteStatus.SENT
    assert q.sent_at is not None
    assert len(mail.outbox) == 1
    assert "quincy@example.com" in mail.outbox[0].to
    assert q.number in mail.outbox[0].subject
    # Lead timeline picks up a QUOTE_SENT activity.
    assert LeadActivity.objects.filter(
        lead=lead, kind=ActivityKind.QUOTE_SENT
    ).count() == 1


@pytest.mark.django_db
def test_send_quote_without_recipient_still_marks_sent(client_record):
    client_record.email = ""
    client_record.save()
    q = Quote.objects.create(client=client_record)
    sent = send_quote(q)
    q.refresh_from_db()
    assert sent is False
    assert q.status == QuoteStatus.SENT
    assert mail.outbox == []


@pytest.mark.django_db
def test_accept_creates_invoice_and_converts_lead(lead_with_quote):
    lead, q = lead_with_quote
    invoice = accept_quote(
        q, accepted_by_name="Quincy Q", accepted_ip="10.0.0.1"
    )
    q.refresh_from_db()
    lead.refresh_from_db()

    assert q.status == QuoteStatus.ACCEPTED
    assert q.accepted_at is not None
    assert q.accepted_by_name == "Quincy Q"
    assert q.converted_invoice_id == invoice.pk

    # Lead is converted into a client and won.
    assert lead.stage == LeadStage.WON
    assert lead.converted_client_id is not None
    assert q.client_id == lead.converted_client_id

    # Invoice mirrors the quote's lines.
    assert invoice.kind == Invoice.Kind.ONE_OFF
    assert invoice.status == Invoice.Status.DRAFT
    assert invoice.total == Decimal("1200.00")
    assert invoice.lines.count() == 1
    line = invoice.lines.first()
    assert line.description == "Smart home install"
    assert line.line_total == Decimal("1200.00")


@pytest.mark.django_db
def test_accept_is_idempotent(lead_with_quote):
    _, q = lead_with_quote
    inv1 = accept_quote(q)
    inv2 = accept_quote(q)
    assert inv1.pk == inv2.pk
    assert Invoice.objects.count() == 1


@pytest.mark.django_db
def test_reject_records_reason(client_record):
    q = Quote.objects.create(client=client_record)
    reject_quote(q, reason="Budget gone for the year")
    q.refresh_from_db()
    assert q.status == QuoteStatus.REJECTED
    assert q.rejected_at is not None
    assert "Budget" in q.rejection_reason


# -----------------------------------------------------------------
# Public accept link
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_public_get_renders_quote(client, lead_with_quote):
    _, q = lead_with_quote
    resp = client.get(f"/q/{q.accept_token}/")
    assert resp.status_code == 200
    assert q.number.encode() in resp.content
    assert b"Smart home install" in resp.content


@pytest.mark.django_db
def test_public_accept_creates_invoice(client, lead_with_quote):
    lead, q = lead_with_quote
    resp = client.post(
        f"/q/{q.accept_token}/",
        data={"action": "accept", "name": "Quincy Q"},
    )
    assert resp.status_code == 200
    q.refresh_from_db()
    assert q.status == QuoteStatus.ACCEPTED
    assert q.converted_invoice_id is not None


@pytest.mark.django_db
def test_public_accept_requires_name(client, lead_with_quote):
    _, q = lead_with_quote
    resp = client.post(
        f"/q/{q.accept_token}/", data={"action": "accept", "name": ""}
    )
    assert resp.status_code == 200
    q.refresh_from_db()
    assert q.status == QuoteStatus.DRAFT
    assert b"Please type your name" in resp.content


@pytest.mark.django_db
def test_public_expired_quote_blocks_accept(client, client_record):
    q = Quote.objects.create(
        client=client_record,
        valid_until=timezone.localdate() - timedelta(days=1),
        status=QuoteStatus.SENT,
    )
    resp = client.post(
        f"/q/{q.accept_token}/", data={"action": "accept", "name": "Anyone"}
    )
    assert resp.status_code == 410
    q.refresh_from_db()
    assert q.status == QuoteStatus.SENT  # still not accepted


@pytest.mark.django_db
def test_public_reject(client, lead_with_quote):
    lead, q = lead_with_quote
    resp = client.post(
        f"/q/{q.accept_token}/",
        data={"action": "reject", "reason": "Going with someone else"},
    )
    assert resp.status_code == 200
    q.refresh_from_db()
    assert q.status == QuoteStatus.REJECTED
    assert "someone else" in q.rejection_reason


# -----------------------------------------------------------------
# Portal CRUD (staff-only)
# -----------------------------------------------------------------


@pytest.fixture
def auth_client(client, engineer_user):
    engineer_user.totp_enabled = True
    engineer_user.set_totp_secret("JBSWY3DPEHPK3PXP")
    engineer_user.save()
    client.force_login(engineer_user)
    return client


@pytest.mark.django_db
def test_portal_create_quote_with_lines(auth_client, client_record):
    resp = auth_client.post(
        reverse("portal:quote_create"),
        data={
            "client": client_record.pk,
            "valid_until": (timezone.localdate() + timedelta(days=14)).isoformat(),
            "tax": "0",
            "currency": "GBP",
            "notes": "Take 2 weeks.",
            "line-description": ["UniFi UDM-Pro", "Install"],
            "line-quantity": ["1", "4"],
            "line-unit_amount": ["400.00", "75.00"],
        },
    )
    assert resp.status_code == 302
    q = Quote.objects.first()
    assert q.lines.count() == 2
    assert q.total == Decimal("700.00")


@pytest.mark.django_db
def test_portal_send_quote(auth_client, client_record):
    client_record.email = "test@example.com"
    client_record.save()
    q = Quote.objects.create(client=client_record)
    QuoteLine.objects.create(
        quote=q, description="Visit", quantity=1, unit_amount=Decimal("75")
    )
    resp = auth_client.post(reverse("portal:quote_send", args=[q.pk]))
    assert resp.status_code == 302
    q.refresh_from_db()
    assert q.status == QuoteStatus.SENT
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_portal_blocks_client_users(client, db, client_record):
    from accounts.models import User

    cu = User.objects.create_user(
        email="cu_q@example.com",
        password="password123",
        role=User.Role.CLIENT,
        client=client_record,
    )
    client.force_login(cu)
    resp = client.get(reverse("portal:quote_list"))
    assert resp.status_code == 302
    assert "/dashboard/" in resp.url


# -----------------------------------------------------------------
# API
# -----------------------------------------------------------------


@pytest.fixture
def api(engineer_user):
    api = APIClient()
    api.force_authenticate(engineer_user)
    return api


@pytest.mark.django_db
def test_api_create_quote_with_lines(api, client_record):
    resp = api.post(
        "/api/v1/quotes/quotes/",
        data={
            "client": client_record.pk,
            "valid_until": (timezone.localdate() + timedelta(days=14)).isoformat(),
            "lines": [
                {"description": "Switch", "quantity": "1", "unit_amount": "120.00"},
                {"description": "Cable", "quantity": "2", "unit_amount": "10.00"},
            ],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["total"] == "140.00"


@pytest.mark.django_db
def test_api_send_endpoint(api, client_record):
    client_record.email = "rx@example.com"
    client_record.save()
    q = Quote.objects.create(client=client_record)
    QuoteLine.objects.create(
        quote=q, description="Visit", quantity=1, unit_amount=Decimal("75")
    )
    resp = api.post(f"/api/v1/quotes/quotes/{q.pk}/send/")
    assert resp.status_code == 200
    assert resp.data["sent"] is True


# -----------------------------------------------------------------
# Stale-quote sweeper
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_expire_stale_quotes(client_record):
    q1 = Quote.objects.create(
        client=client_record,
        valid_until=timezone.localdate() - timedelta(days=1),
        status=QuoteStatus.SENT,
    )
    q2 = Quote.objects.create(
        client=client_record,
        valid_until=timezone.localdate() - timedelta(days=2),
        status=QuoteStatus.DRAFT,
    )
    q3 = Quote.objects.create(
        client=client_record,
        valid_until=timezone.localdate() + timedelta(days=2),
        status=QuoteStatus.SENT,
    )
    from .tasks import expire_stale_quotes

    expire_stale_quotes()
    q1.refresh_from_db(); q2.refresh_from_db(); q3.refresh_from_db()
    assert q1.status == QuoteStatus.EXPIRED
    assert q2.status == QuoteStatus.EXPIRED
    assert q3.status == QuoteStatus.SENT
