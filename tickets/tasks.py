"""Celery tasks for the tickets app."""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def generate_scheduled_tickets() -> str:
    """Daily sweep — open a Ticket for every MaintenanceSchedule that's due.

    A schedule is "due" when `active=True` and `next_run_at <= today`.
    After creating the ticket the schedule advances by one cadence
    interval; if it's still overdue we keep advancing until it lands
    in the future so a long-neglected schedule doesn't spam tickets
    on subsequent daily runs.
    """
    from .models import MaintenanceSchedule, Ticket

    today = timezone.localdate()
    qs = MaintenanceSchedule.objects.filter(
        active=True, next_run_at__lte=today
    ).select_related("client", "system", "default_assignee")

    created = 0
    for sched in qs:
        Ticket.objects.create(
            client=sched.client,
            system=sched.system,
            subject=sched.template_subject,
            description=sched.template_description,
            priority=sched.priority or "",
            assigned_to=sched.default_assignee,
        )
        new_next = sched.compute_next_run_at()
        while new_next <= today:
            new_next = sched.compute_next_run_at(from_date=new_next)
        sched.last_run_at = today
        sched.next_run_at = new_next
        sched.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
        created += 1
    return f"generate_scheduled_tickets: {created} created"


@shared_task
def poll_inbound_mail() -> str:
    """Pull UNSEEN messages from the inbound IMAP mailbox and ingest them.

    Each message is flagged Seen after we've handed it to `ingest()` —
    even if `ingest` dropped it (unknown sender, no client link) — so
    we don't loop on the same message. Network/parse failures leave the
    message unread and surface in logs for the next run.

    No-op when `INBOUND_IMAP_HOST` is empty so dev and CI don't reach
    out to an IMAP server.
    """
    host = getattr(settings, "INBOUND_IMAP_HOST", "") or ""
    if not host:
        return "inbound mail disabled"

    import imaplib

    from .inbound import ingest

    imap = imaplib.IMAP4_SSL(host, getattr(settings, "INBOUND_IMAP_PORT", 993))
    try:
        imap.login(settings.INBOUND_IMAP_USER, settings.INBOUND_IMAP_PASSWORD)
        imap.select(getattr(settings, "INBOUND_IMAP_MAILBOX", "INBOX"))
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return f"search failed: {status}"

        ingested = 0
        for mid in data[0].split():
            status, fetched = imap.fetch(mid, "(RFC822)")
            if status != "OK" or not fetched or not fetched[0]:
                continue
            raw = fetched[0][1]
            try:
                result = ingest(raw)
            except Exception:
                logger.exception("inbound ingest failed for message %s", mid)
                continue
            imap.store(mid, "+FLAGS", "\\Seen")
            if result.ticket is not None:
                ingested += 1
        return f"ingested {ingested} message(s)"
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass
