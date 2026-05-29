"""Celery tasks: ticket-update emails, SLA-warning sweep, push fan-out."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .models import DeviceToken, Notification, OutboundWebhook

logger = logging.getLogger(__name__)


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

    subject = f"[Luma Tech Solutions #{ticket.pk}] {ticket.subject} — {event}"
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
def send_weekly_client_digest() -> str:
    """Fri-9am beat — fan out the per-client weekly summary email."""
    from .digests import send_digests

    n = send_digests()
    return f"weekly digest: {n} emails sent"


@shared_task
def send_csat_email(ticket_id: int):
    """Email a single-use CSAT survey link to the client who opened the ticket.

    Idempotent: a Ticket has at most one CsatResponse (OneToOne), so a
    repeat call returns "already-sent" without emailing twice.
    """
    from tickets.models import CsatResponse, Ticket

    try:
        ticket = Ticket.objects.select_related("client", "created_by").get(
            pk=ticket_id
        )
    except Ticket.DoesNotExist:
        return "missing"

    csat, was_new = CsatResponse.objects.get_or_create(ticket=ticket)
    if not was_new:
        return "already-sent"

    recipient = None
    if ticket.created_by and ticket.created_by.email:
        recipient = ticket.created_by.email
    elif ticket.client.email:
        recipient = ticket.client.email
    if not recipient:
        return "no-recipient"

    subject = f"How did we do? — Ticket #{ticket.pk}"
    link = f"{settings.SITE_URL.rstrip('/')}/csat/{csat.token}/"
    body = (
        f"Hi,\n\n"
        f"We've closed ticket #{ticket.pk} — {ticket.subject}.\n\n"
        f"Could you take 10 seconds to rate how we did?\n\n"
        f"{link}\n\n"
        f"Thanks,\nLuma Tech Solutions\n"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
        fail_silently=False,
    )
    return "sent"


@shared_task
def check_sla_warnings():
    """Run every 5 minutes (Celery beat) — alert on tickets close to / past SLA."""
    from tickets.models import Ticket

    threshold_minutes = 30
    now = timezone.now()
    cutoff = now + timedelta(minutes=threshold_minutes)
    qs = (
        Ticket.objects.open()
        .filter(sla_paused_at__isnull=True)
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


# Errors from firebase_admin.messaging that mean a device token is gone for good.
_DEAD_TOKEN_ERRORS = frozenset(
    {"UNREGISTERED", "INVALID_ARGUMENT", "NOT_FOUND", "InvalidRegistration"}
)


class _PushMessage:
    """Platform-neutral push payload. Translated into firebase_admin.messaging.Message
    inside ``_fcm_send`` so the rest of the module (and tests) doesn't need the SDK."""

    __slots__ = ("token", "title", "body", "data")

    def __init__(self, token, title, body, data):
        self.token = token
        self.title = title
        self.body = body
        self.data = data


def _fcm_send(messages):
    """Send a batch via firebase_admin.messaging. Patched out in tests."""
    from firebase_admin import messaging

    fcm_messages = [
        messaging.Message(
            token=m.token,
            notification=messaging.Notification(title=m.title, body=m.body),
            data=m.data,
        )
        for m in messages
    ]
    return messaging.send_each(fcm_messages)


@shared_task
def send_outbound_webhook(notification_id: int):
    """Fan out a Notification to the recipient's configured outbound webhooks.

    No-op when the user has no webhooks (or none that match the event
    filter). Each call updates last_called_at / last_status on the
    webhook so the user can see the channel is healthy at a glance.
    The HTTP call is best-effort: a failing webhook is logged + recorded
    but never raises (that would re-queue the task indefinitely).
    """
    import httpx

    try:
        notif = Notification.objects.select_related(
            "user", "related_ticket"
        ).get(pk=notification_id)
    except Notification.DoesNotExist:
        return "notification missing"

    qs = OutboundWebhook.objects.filter(user=notif.user, enabled=True)
    delivered = 0
    for hook in qs:
        if hook.event_filter and notif.type not in hook.event_filter:
            continue
        payload = _format_webhook_payload(notif, hook)
        try:
            resp = httpx.post(hook.url, json=payload, timeout=10)
            hook.last_status = f"{resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            hook.last_status = f"err:{type(exc).__name__}"[:64]
            logger.warning(
                "outbound webhook %s failed: %s", hook.pk, exc
            )
        hook.last_called_at = timezone.now()
        hook.save(update_fields=["last_status", "last_called_at"])
        delivered += 1
    return f"outbound webhooks: {delivered} attempted"


def _format_webhook_payload(notif, hook):
    """Translate a Notification into the body shape each channel expects."""
    text = f"*{notif.title}*"
    if notif.body:
        text += f"\n{notif.body}"
    if hook.format == OutboundWebhook.Format.SLACK:
        return {"text": text}
    if hook.format == OutboundWebhook.Format.TEAMS:
        return {"@type": "MessageCard", "text": text}
    # generic
    return {
        "type": notif.type,
        "title": notif.title,
        "body": notif.body,
        "ticket_id": notif.related_ticket_id,
        "created_at": notif.created_at.isoformat(),
    }


@shared_task
def send_push(notification_id: int):
    """Fan out a Notification to the recipient's active push devices.

    No-op when FCM_ENABLED is false so dev and CI don't try to reach
    Firebase. Tokens that come back with a permanent error are deactivated
    so the next run skips them.
    """
    if not getattr(settings, "FCM_ENABLED", False):
        return "fcm disabled"

    try:
        notif = Notification.objects.select_related("user", "related_ticket").get(
            pk=notification_id
        )
    except Notification.DoesNotExist:
        return "notification missing"

    # Quiet-hours suppression: skip non-critical push during the user's
    # configured window. Critical SLA / ticket-update can still go
    # through when ``quiet_hours_critical_override`` is on (default).
    user = notif.user
    if user.is_in_quiet_hours():
        is_critical = (
            notif.related_ticket is not None
            and notif.related_ticket.priority == "critical"
        ) or notif.type == Notification.Type.SLA_WARNING
        if not (is_critical and user.quiet_hours_critical_override):
            return "quiet hours — suppressed"

    tokens = list(
        DeviceToken.objects.filter(user=notif.user, is_active=True).order_by("pk")
    )
    if not tokens:
        return "no devices"

    data = {
        "type": notif.type,
        "notification_id": str(notif.pk),
    }
    if notif.related_ticket_id:
        data["ticket_id"] = str(notif.related_ticket_id)
        data["route"] = f"/tickets/{notif.related_ticket_id}"

    messages = [
        _PushMessage(
            token=t.token, title=notif.title, body=notif.body or "", data=data
        )
        for t in tokens
    ]
    response = _fcm_send(messages)

    dead_tokens = []
    for token_obj, resp in zip(tokens, response.responses, strict=False):
        if resp.success:
            continue
        code = getattr(resp.exception, "code", None) or getattr(
            resp.exception, "__class__", type("", (), {})
        ).__name__
        if code in _DEAD_TOKEN_ERRORS:
            dead_tokens.append(token_obj.pk)
        else:
            logger.warning(
                "push failed for token %s: %s", token_obj.pk, resp.exception
            )
    if dead_tokens:
        DeviceToken.objects.filter(pk__in=dead_tokens).update(is_active=False)

    notif.push_sent = True
    notif.save(update_fields=["push_sent"])
    return f"push sent: {response.success_count}/{len(messages)}"
