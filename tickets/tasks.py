"""Celery tasks for the tickets app."""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_monthly_reports(year: int | None = None, month: int | None = None) -> str:
    """1st-of-month rollup: email a PDF summary to every care-plan client.

    With no args, targets the previous calendar month. Emails the
    primary Contact when present; falls back to the client's main email.
    Clients on care_plan_tier=none are skipped.
    """
    from django.conf import settings
    from django.core.mail import EmailMessage

    from clients.models import CarePlanTier, Client

    from .reports import build_monthly_report_pdf

    today = timezone.localdate()
    if year is None or month is None:
        if today.month == 1:
            year, month = today.year - 1, 12
        else:
            year, month = today.year, today.month - 1

    sent = 0
    qs = Client.objects.exclude(care_plan_tier=CarePlanTier.NONE)
    for client in qs:
        primary = client.contacts.filter(is_primary=True).exclude(email="").first()
        recipient = primary.email if primary else (client.email or "")
        if not recipient:
            logger.info("client #%s has no recipient — skipping report", client.pk)
            continue
        try:
            pdf_bytes = build_monthly_report_pdf(client, year, month)
        except Exception:
            logger.exception("monthly report failed for client #%s", client.pk)
            continue

        subject = (
            f"Your Luma Tech Solutions monthly report — {year}-{month:02d}"
        )
        body = (
            f"Hi,\n\nPlease find attached your monthly support summary "
            f"covering {month:02d}/{year}.\n\nThanks,\nLuma Tech Solutions\n"
        )
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        email.attach(
            f"luma-report-{client.pk}-{year}-{month:02d}.pdf",
            pdf_bytes,
            "application/pdf",
        )
        email.send(fail_silently=False)
        sent += 1

    return f"send_monthly_reports: {sent} sent"


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


def is_after_hours(when=None) -> bool:
    """Is ``when`` outside Marco's configured business hours?

    Override the defaults via two settings:

    - ``BUSINESS_HOURS`` = (start_hour, end_hour) — 24h ints, default (9, 18).
    - ``BUSINESS_DAYS`` = iterable of weekday ints (Mon=0), default Mon-Fri.

    Always returns True (i.e. "after hours") when called with a naive
    datetime so the caller can't accidentally enable the autoresponder
    without timezone-aware datetimes.
    """
    if when is None:
        when = timezone.now()
    if timezone.is_naive(when):
        return True
    start, end = getattr(settings, "BUSINESS_HOURS", (9, 18))
    days = set(getattr(settings, "BUSINESS_DAYS", range(0, 5)))
    local = timezone.localtime(when)
    if local.weekday() not in days:
        return True
    return not (start <= local.hour < end)


@shared_task
def after_hours_acknowledge(ticket_id: int) -> str:
    """Send a friendly auto-ack when a ticket lands outside business hours.

    Behaviour:
    - Adds a public TicketNote with either an AI-drafted message (when
      ANTHROPIC_API_KEY is set) or a simple canned acknowledgement.
    - Adds an internal note recording that we treated this as after-hours.
    - Critical tickets get an immediate Notification fan-out to
      admins/engineers (regular SLA path is hourly-ish; this is faster).

    No-op when the ``after_hours_oncall`` feature flag is off or the
    ticket arrived during business hours.
    """
    from features import is_enabled

    from .ai import draft_reply
    from .models import Ticket, TicketNote

    if not is_enabled("after_hours_oncall"):
        return "after_hours_oncall disabled"

    try:
        ticket = Ticket.objects.select_related("client").get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return "missing"

    if not is_after_hours(ticket.created_at):
        return "in business hours — no-op"

    # AI-drafted ack if available; otherwise the canned fallback.
    drafted = draft_reply(ticket)
    if drafted:
        ack = drafted
    else:
        ack = (
            "Hi — your ticket landed outside our usual hours (Mon-Fri "
            "09:00-18:00 UK). We've logged it; an engineer will respond "
            "as soon as we're back. For genuine emergencies, please mark "
            "the ticket as Critical and we'll be paged immediately."
        )

    TicketNote.objects.create(
        ticket=ticket,
        author=None,
        body=ack,
        internal=False,
    )
    TicketNote.objects.create(
        ticket=ticket,
        author=None,
        body="[after-hours auto-acknowledged]",
        internal=True,
    )

    # Critical → immediately wake engineers via Notification (the signal
    # fans out to push + outbound webhooks).
    if ticket.priority == Ticket.Priority.CRITICAL:
        from django.contrib.auth import get_user_model

        from notifications.models import Notification

        User = get_user_model()
        for u in User.objects.filter(
            role__in=["admin", "engineer"], is_active=True
        ):
            Notification.objects.create(
                user=u,
                type=Notification.Type.NEW_TICKET,
                title=f"After-hours critical: #{ticket.pk}",
                body=f"{ticket.client.name} — {ticket.subject}",
                related_ticket=ticket,
            )

    return "acknowledged"


@shared_task
def triage_new_ticket(ticket_id: int) -> str:
    """Ask Claude to suggest priority + tags for a freshly-opened ticket.

    Applies the suggestion when found and records the reasoning as an
    internal note so engineers can see why the AI made the call. No-op
    when the ``ai_triage`` feature flag is off or ANTHROPIC_API_KEY is
    unset.
    """
    from features import is_enabled

    from .ai import triage_ticket
    from .models import Ticket, TicketNote, TicketTag

    if not is_enabled("ai_triage"):
        return "ai_triage disabled"

    try:
        ticket = Ticket.objects.select_related("client").get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return "missing"

    result = triage_ticket(ticket)
    if result is None:
        return "no result"

    changes = []
    if result.get("priority") and result["priority"] != ticket.priority:
        ticket.priority = result["priority"]
        ticket.save(update_fields=["priority"])
        changes.append(f"priority -> {result['priority']}")
    for slug in result.get("tag_slugs", []):
        tag = TicketTag.objects.filter(slug=slug).first()
        if tag is not None and not ticket.tags.filter(pk=tag.pk).exists():
            ticket.tags.add(tag)
            changes.append(f"tag +{slug}")

    body_parts = ["[AI triage]"]
    body_parts.append(result.get("reasoning") or "(no reasoning supplied)")
    if changes:
        body_parts.append("Applied: " + ", ".join(changes))
    else:
        body_parts.append("No changes applied.")
    TicketNote.objects.create(
        ticket=ticket,
        author=None,
        body="\n\n".join(body_parts),
        internal=True,
    )
    return f"triaged: {', '.join(changes) or 'no-op'}"


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
