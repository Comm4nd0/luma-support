"""Weekly client digest — a Friday-9am email per opted-in client.

The digest is a single short HTML/plaintext message summarising the
last 7 days for the client's account: tickets opened/closed, hours
spent, the next scheduled maintenance, and a couple of KB articles
they might find handy. Quiet by default — clients with
``weekly_digest_opt_in=False`` are skipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Count, Q, Sum
from django.utils import timezone

from clients.models import Client


@dataclass
class DigestStats:
    opened: int
    closed: int
    hours_logged: Decimal
    next_maintenance: str  # ISO date or "—"
    suggested_articles: list[tuple[str, str]]  # (title, slug)

    @property
    def has_signal(self) -> bool:
        """True if there's anything worth telling the client about."""
        return any(
            (
                self.opened,
                self.closed,
                self.hours_logged,
                self.next_maintenance != "—",
            )
        )


def compose_for(client: Client, *, now=None) -> DigestStats:
    """Build the stats payload for one client. Pure function, no I/O
    beyond the DB so it's safe to call from a view for a preview."""
    from knowledge.models import Article
    from tickets.models import MaintenanceSchedule, Ticket, TimeEntry

    now = now or timezone.now()
    since = now - timedelta(days=7)
    today = timezone.localdate()

    tickets = Ticket.objects.filter(client=client)
    by_status = tickets.aggregate(
        opened=Count("id", filter=Q(created_at__gte=since)),
        closed=Count(
            "id",
            filter=Q(
                resolved_at__gte=since,
                status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED],
            ),
        ),
    )
    minutes = (
        TimeEntry.objects.filter(
            ticket__client=client, created_at__gte=since
        ).aggregate(total=Sum("minutes"))["total"]
        or 0
    )
    next_m = (
        MaintenanceSchedule.objects.filter(
            client=client, active=True, next_run_at__gte=today
        )
        .order_by("next_run_at")
        .first()
    )
    next_at = next_m.next_run_at.isoformat() if next_m else "—"

    # Two recent client-visible articles as light reading; never an N+1
    # since the result is small and bounded.
    articles = (
        Article.objects.for_client(client)
        .order_by("-published_at")[:2]
    )
    article_pairs = [(a.title, a.slug) for a in articles]

    return DigestStats(
        opened=by_status["opened"] or 0,
        closed=by_status["closed"] or 0,
        hours_logged=(Decimal(minutes) / Decimal(60)).quantize(Decimal("0.1")),
        next_maintenance=next_at,
        suggested_articles=article_pairs,
    )


def _render(client: Client, stats: DigestStats) -> tuple[str, str]:
    subject = f"Your Luma weekly summary — {timezone.localdate():%d %b %Y}"
    lines = [
        f"Hi {client.name},",
        "",
        "Here's a quick summary of the last 7 days on your account:",
        "",
        f"• Tickets opened: {stats.opened}",
        f"• Tickets closed: {stats.closed}",
        f"• Hours spent on your account: {stats.hours_logged}",
        f"• Next scheduled maintenance: {stats.next_maintenance}",
    ]
    if stats.suggested_articles:
        lines += ["", "Articles you might find useful:"]
        base = getattr(settings, "SITE_URL", "").rstrip("/")
        for title, slug in stats.suggested_articles:
            lines.append(f"  · {title} — {base}/kb/{slug}/")
    lines += ["", "Thanks,", "Luma Tech Solutions"]
    return subject, "\n".join(lines)


def send_digests(now=None) -> int:
    """Send the weekly digest to every opted-in client with a recipient.

    Returns the number of emails actually sent. Clients with no signal
    in the last 7 days are skipped so we don't fill inboxes with
    "nothing happened" notes.
    """
    sent = 0
    qs = Client.objects.filter(weekly_digest_opt_in=True)
    for client in qs:
        stats = compose_for(client, now=now)
        if not stats.has_signal:
            continue
        primary = client.contacts.filter(is_primary=True).exclude(email="").first()
        recipient = primary.email if primary else (client.email or "")
        if not recipient:
            continue
        subject, body = _render(client, stats)
        EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        ).send(fail_silently=False)
        sent += 1
    return sent
