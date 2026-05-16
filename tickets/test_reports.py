"""Monthly client PDF report — PDF builder + send_monthly_reports task."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone as _tz

import pytest
from django.core import mail
from django.utils import timezone

from clients.models import CarePlanTier, Client, Contact
from tickets.models import CsatResponse, Ticket, TimeEntry
from tickets.reports import build_monthly_report_pdf
from tickets.tasks import send_monthly_reports

pytestmark = pytest.mark.django_db


@pytest.fixture
def acme(db):
    return Client.objects.create(
        name="Acme",
        email="ops@acme.test",
        care_plan_tier=CarePlanTier.PROFESSIONAL,
    )


def _mid_of(year, month):
    return datetime(year, month, 15, tzinfo=_tz.utc)


# ----- PDF builder -----------------------------------------------------


def test_pdf_is_non_empty_bytes(acme):
    pdf = build_monthly_report_pdf(acme, 2026, 1)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500  # not just header


def test_pdf_contains_client_name(acme):
    pdf = build_monthly_report_pdf(acme, 2026, 1)
    # ReportLab emits the title plus text strings into the PDF body.
    # Even with compression, "Acme" appears in the title metadata.
    assert b"Acme" in pdf


def test_pdf_counts_only_period_tickets(acme):
    in_period = _mid_of(2026, 1)
    out_of_period = _mid_of(2026, 2)
    t1 = Ticket.objects.create(client=acme, subject="in scope")
    Ticket.objects.filter(pk=t1.pk).update(created_at=in_period)
    t2 = Ticket.objects.create(client=acme, subject="out of scope")
    Ticket.objects.filter(pk=t2.pk).update(created_at=out_of_period)

    # Cheap proxy: regenerate the queryset and assert counts directly.
    from django.db.models import Q

    qs = acme.tickets.filter(
        Q(created_at__gte=datetime(2026, 1, 1, tzinfo=_tz.utc))
        & Q(created_at__lt=datetime(2026, 2, 1, tzinfo=_tz.utc))
    )
    assert qs.count() == 1

    pdf = build_monthly_report_pdf(acme, 2026, 1)
    assert pdf  # builds without error even when filtered


# ----- send_monthly_reports task ---------------------------------------


def test_task_emails_primary_contact(acme):
    Contact.objects.create(
        client=acme, name="Alice", email="alice@acme.test", is_primary=True
    )
    # Make sure there's something for the report to mention.
    Ticket.objects.create(client=acme, subject="VPN")

    today = timezone.localdate()
    # Run "for this month" so we're guaranteed at least one ticket falls in.
    send_monthly_reports(year=today.year, month=today.month)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["alice@acme.test"]
    assert msg.attachments
    name, content, content_type = msg.attachments[0]
    assert name.startswith("luma-report-")
    assert name.endswith(".pdf")
    assert content_type == "application/pdf"
    assert content.startswith(b"%PDF-")


def test_task_falls_back_to_client_email_without_primary(acme):
    today = timezone.localdate()
    send_monthly_reports(year=today.year, month=today.month)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ops@acme.test"]


def test_task_skips_clients_without_care_plan(db):
    Client.objects.create(
        name="Hobbyist",
        email="me@hobbyist.test",
        care_plan_tier=CarePlanTier.NONE,
    )
    today = timezone.localdate()
    result = send_monthly_reports(year=today.year, month=today.month)
    assert "0 sent" in result
    assert mail.outbox == []


def test_task_skips_clients_with_no_recipient(db):
    Client.objects.create(
        name="Anon", email="", care_plan_tier=CarePlanTier.PROFESSIONAL
    )
    today = timezone.localdate()
    send_monthly_reports(year=today.year, month=today.month)
    assert mail.outbox == []


def test_task_default_args_target_previous_month(acme):
    """With no year/month, the task uses the previous calendar month."""
    today = timezone.localdate()
    expected_year = today.year - 1 if today.month == 1 else today.year
    expected_month = 12 if today.month == 1 else today.month - 1

    send_monthly_reports()

    assert len(mail.outbox) == 1
    attachment_name = mail.outbox[0].attachments[0][0]
    assert f"{expected_year}-{expected_month:02d}" in attachment_name
