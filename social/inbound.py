"""Convert a SocialInboxItem into a Ticket.

Social DMs/mentions usually come from prospects, not existing clients,
so we don't require Marco to pre-create a Client row. If no `client_id`
is passed, we auto-create a HOME-type Client named after the author's
handle and tag it in notes as a social lead — Marco can rename later.
"""
from __future__ import annotations

from clients.models import Client, CustomerType
from tickets.models import Ticket

from .models import InboxStatus, SocialInboxItem


def convert_inbox_item_to_ticket(
    item: SocialInboxItem,
    actor,
    *,
    client_id: int | None = None,
) -> Ticket:
    """Idempotent: if the item already has a converted_ticket, return it."""
    if item.converted_ticket_id:
        return item.converted_ticket

    if client_id:
        client = Client.objects.get(pk=client_id)
    else:
        author = (
            item.author_display
            or item.author_handle
            or f"{item.account.get_platform_display()} contact"
        )
        client = Client.objects.create(
            name=f"Social lead: {author}"[:200],
            customer_type=CustomerType.HOME,
            notes=(
                f"Auto-created from {item.account.get_platform_display()} "
                f"{item.get_kind_display()} on "
                f"{item.received_at:%Y-%m-%d %H:%M %Z}.\n"
                f"Permalink: {item.permalink}"
            ),
        )

    subject_source = item.preview or "(no message body)"
    subject = (subject_source[:200]).strip() or "(no message body)"
    description = (
        f"{item.account.get_platform_display()} {item.get_kind_display()} "
        f"from @{item.author_handle or 'unknown'} "
        f"({item.author_display or '—'})\n"
        f"Received: {item.received_at:%Y-%m-%d %H:%M %Z}\n"
        f"Permalink: {item.permalink}\n\n"
        f"{item.preview or ''}"
    )

    ticket = Ticket.objects.create(
        client=client,
        subject=subject,
        description=description,
        created_by=actor,
    )

    item.converted_ticket = ticket
    item.status = InboxStatus.CONVERTED
    item.save(update_fields=["converted_ticket", "status"])
    return ticket
