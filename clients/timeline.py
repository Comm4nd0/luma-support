"""Unified per-client communication timeline.

View-time union of Ticket, Quote, Invoice and pre-conversion
LeadActivity events. No storage — every render rebuilds from the
underlying tables, which keeps the timeline honest after a delete.

Each event is a small dataclass with a discriminator string so the
template can route on `kind` without isinstance() checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass
class TimelineEvent:
    kind: str           # "ticket" | "ticket_note" | "quote" | "invoice" | "lead_activity"
    occurred_at: datetime
    title: str
    body: str = ""
    url: str = ""       # in-app link (e.g. /tickets/42/), optional
    pill: str = ""      # e.g. "open", "paid" — used for visual chip


def for_client(client) -> list[TimelineEvent]:
    """Return all events for a client, newest first."""
    events: list[TimelineEvent] = []
    events.extend(_tickets(client))
    events.extend(_ticket_notes(client))
    events.extend(_quotes(client))
    events.extend(_invoices(client))
    events.extend(_lead_activities(client))
    events.sort(key=lambda e: e.occurred_at, reverse=True)
    return events


def _tickets(client) -> Iterable[TimelineEvent]:
    from tickets.models import Ticket

    qs = client.tickets.all().only(
        "pk", "subject", "status", "priority", "created_at"
    )
    for t in qs:
        yield TimelineEvent(
            kind="ticket",
            occurred_at=t.created_at,
            title=f"Ticket #{t.pk}: {t.subject}",
            body=f"{t.get_priority_display()} · {t.get_status_display()}",
            url=f"/tickets/{t.pk}/",
            pill=t.status,
        )


def _ticket_notes(client):
    from tickets.models import TicketNote

    qs = TicketNote.objects.filter(
        ticket__client_id=client.pk, internal=False
    ).select_related("ticket", "author")
    for n in qs:
        yield TimelineEvent(
            kind="ticket_note",
            occurred_at=n.created_at,
            title=f"Note on ticket #{n.ticket_id}",
            body=n.body[:280],
            url=f"/tickets/{n.ticket_id}/",
            pill="note",
        )


def _quotes(client):
    try:
        from quotes.models import Quote
    except Exception:
        return
    for q in Quote.objects.filter(client_id=client.pk):
        yield TimelineEvent(
            kind="quote",
            occurred_at=q.created_at,
            title=f"Quote {q.number}",
            body=f"{q.currency} {q.total} · {q.get_status_display()}",
            url=f"/quotes/{q.pk}/",
            pill=q.status,
        )
        if q.accepted_at:
            yield TimelineEvent(
                kind="quote",
                occurred_at=q.accepted_at,
                title=f"Quote {q.number} accepted",
                body=q.accepted_by_name or "",
                url=f"/quotes/{q.pk}/",
                pill="accepted",
            )


def _invoices(client):
    from billing.models import Invoice

    for inv in Invoice.objects.filter(client_id=client.pk):
        yield TimelineEvent(
            kind="invoice",
            occurred_at=inv.created_at,
            title=f"Invoice #{inv.pk} {inv.get_kind_display()}",
            body=f"{inv.currency} {inv.total} · {inv.get_status_display()}",
            url=f"/billing/invoices/{inv.pk}/",
            pill=inv.status,
        )
        if inv.paid_at:
            yield TimelineEvent(
                kind="invoice",
                occurred_at=inv.paid_at,
                title=f"Invoice #{inv.pk} paid",
                body=f"{inv.currency} {inv.total}",
                url=f"/billing/invoices/{inv.pk}/",
                pill="paid",
            )


def _lead_activities(client):
    """Pre-conversion lead notes/calls/emails, surfaced post-conversion."""
    try:
        from leads.models import LeadActivity
    except Exception:
        return
    lead_ids = list(
        client.origin_leads.values_list("pk", flat=True)
    )
    if not lead_ids:
        return
    qs = LeadActivity.objects.filter(lead_id__in=lead_ids).select_related(
        "actor"
    )
    for a in qs:
        yield TimelineEvent(
            kind="lead_activity",
            occurred_at=a.occurred_at,
            title=f"{a.get_kind_display()} (lead)",
            body=a.body,
            pill=a.kind,
        )
