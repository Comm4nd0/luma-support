"""Tests for the per-client unified timeline."""
from decimal import Decimal

import pytest
from django.utils import timezone

from billing.models import Invoice
from leads.models import ActivityKind, Lead, LeadActivity
from tickets.models import Ticket, TicketNote

from .timeline import for_client


@pytest.mark.django_db
def test_timeline_collects_tickets_invoices_quotes(client_record):
    Ticket.objects.create(
        client=client_record,
        subject="Wi-Fi flaky",
        description="x",
        priority=Ticket.Priority.HIGH,
    )
    Invoice.objects.create(
        client=client_record,
        kind=Invoice.Kind.ONE_OFF,
        status=Invoice.Status.DRAFT,
        total=Decimal("100"),
        subtotal=Decimal("100"),
    )
    events = for_client(client_record)
    kinds = {e.kind for e in events}
    assert "ticket" in kinds
    assert "invoice" in kinds


@pytest.mark.django_db
def test_public_ticket_notes_appear_internal_ones_do_not(client_record, engineer_user):
    t = Ticket.objects.create(
        client=client_record, subject="Q", description="x"
    )
    TicketNote.objects.create(
        ticket=t, author=engineer_user, body="public reply", internal=False
    )
    TicketNote.objects.create(
        ticket=t, author=engineer_user, body="internal", internal=True
    )
    events = for_client(client_record)
    note_events = [e for e in events if e.kind == "ticket_note"]
    assert len(note_events) == 1
    assert note_events[0].body == "public reply"


@pytest.mark.django_db
def test_pre_conversion_lead_activity_appears(engineer_user):
    lead = Lead.objects.create(name="X")
    LeadActivity.objects.create(
        lead=lead,
        kind=ActivityKind.CALL,
        body="left voicemail",
        actor=engineer_user,
    )
    client = lead.convert_to_client(by_user=engineer_user)
    events = for_client(client)
    assert any(e.kind == "lead_activity" for e in events)


@pytest.mark.django_db
def test_events_sorted_newest_first(client_record):
    t1 = Ticket.objects.create(client=client_record, subject="A", description="x")
    t2 = Ticket.objects.create(client=client_record, subject="B", description="x")
    events = [e for e in for_client(client_record) if e.kind == "ticket"]
    # The newer ticket sorts before the older one.
    assert events[0].title.endswith("B")
