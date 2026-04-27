"""Celery tasks: ticket-update emails and SLA-warning sweep."""
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_ticket_update_email(self, ticket_id: int, event: str = "updated"):
    """Send a ticket update email and create in-app notifications.

    `event` is a string like "created", "status:resolved", "status:assigned".
    """
    from tickets.models import Ticket

    try:
        ticket = Ticket.objects.select_related(
            "client", "assigned_to", "created_by"
        ).get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return

    User = get_user_model()
    recipients = set()
    if ticket.assigned_to and ticket.assigned_to.email:
        recipients.add(ticket.assigned_to.email)
    if ticket.created_by and ticket.created_by.email:
        recipients.add(ticket.created_by.email)
    # CC engineers/admins on critical tickets so nothing slips through.
    if ticket.priority == Ticket.Priority.CRITICAL:
        for u in User.objects.filter(role__in=["admin", "engineer"], is_active=True):
            if u.email:
                recipients.add(u.email)

    subject = f"[Luma Support #{ticket.pk}] {ticket.subject} — {event}"
    body = (
        f"Ticket #{ticket.pk} for {ticket.client.name}\n"
        f"Status: {ticket.get_status_display()}\n"
        f"Priority: {ticket.get_priority_display()}\n"
        f"SLA deadline: {ticket.sla_deadline:%Y-%m-%d %H:%M %Z}\n\n"
        f"Subject: {ticket.subject}\n\n"
        f"{ticket.description}\n\n"
        f"View: {settings.SITE_URL}/tickets/{ticket.pk}/\n"
    )

    if recipients:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            list(recipients),
            fail_silently=False,
        )

    # In-app notifications (engineers + admins for critical, assignee otherwise).
    notif_users = []
    if ticket.assigned_to:
        notif_users.append(ticket.assigned_to)
    if ticket.priority == Ticket.Priority.CRITICAL:
        notif_users.extend(
            User.objects.filter(role__in=["admin", "engineer"], is_active=True)
        )

    seen = set()
    for u in notif_users:
        if u.pk in seen:
            continue
        seen.add(u.pk)
        Notification.objects.create(
            user=u,
            type=Notification.Type.NEW_TICKET if event == "created"
                 else Notification.Type.TICKET_UPDATE,
            title=subject,
            body=ticket.subject,
            related_ticket=ticket,
        )


@shared_task
def check_sla_warnings():
    """Run every 5 minutes (Celery beat) — alert on tickets close to / past SLA."""
    from tickets.models import Ticket

    threshold_minutes = 30
    now = timezone.now()
    cutoff = now + timedelta(minutes=threshold_minutes)
    qs = (
        Ticket.objects.open()
        .filter(sla_deadline__lte=cutoff)
        .select_related("assigned_to", "client")
    )

    User = get_user_model()
    notified = 0
    for ticket in qs:
        users = list(
            User.objects.filter(role__in=["admin", "engineer"], is_active=True)
        )
        if ticket.assigned_to and ticket.assigned_to not in users:
            users.append(ticket.assigned_to)

        # Avoid spamming: skip if a SLA_WARNING notification was created
        # for this ticket within the last 25 minutes.
        cutoff_recent = now - timedelta(minutes=25)
        already = Notification.objects.filter(
            related_ticket=ticket,
            type=Notification.Type.SLA_WARNING,
            created_at__gte=cutoff_recent,
        ).exists()
        if already:
            continue

        breach_state = "BREACHED" if ticket.is_breached else "approaching SLA"
        title = f"SLA {breach_state}: #{ticket.pk} {ticket.subject}"
        body = (
            f"Client: {ticket.client.name}\n"
            f"Priority: {ticket.get_priority_display()}\n"
            f"Deadline: {ticket.sla_deadline:%Y-%m-%d %H:%M %Z}\n"
        )
        for u in users:
            Notification.objects.create(
                user=u,
                type=Notification.Type.SLA_WARNING,
                title=title,
                body=body,
                related_ticket=ticket,
            )
            notified += 1

    return f"sla-warnings: {notified} notifications created"
