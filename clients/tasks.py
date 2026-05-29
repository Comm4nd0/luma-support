"""Periodic upkeep for clients.

`check_care_plan_renewals` runs daily, alerts staff at 30/14/7/1 days
before each client's `care_plan_renewal` date and flags overdue ones.
Dedupes per-client per-window via the audit log so a single client
doesn't generate the same alert two days running.
"""
from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from audit import log as audit_log
from audit.models import AuditLog
from notifications.models import Notification
from notifications.tasks import send_push

from .models import CarePlanTier, Client

# Days before renewal where we send a reminder.
_REMIND_AT_DAYS = (30, 14, 7, 1)


@shared_task
def check_care_plan_renewals():
    today = timezone.localdate()

    User = get_user_model()
    staff = list(
        User.objects.filter(role__in=["admin", "engineer"], is_active=True)
    )

    notified = 0
    qs = (
        Client.objects.exclude(care_plan_tier=CarePlanTier.NONE)
        .exclude(care_plan_renewal__isnull=True)
    )
    for client in qs:
        days = (client.care_plan_renewal - today).days
        bucket = _bucket_for(days)
        if bucket is None:
            continue

        if _already_alerted(client, bucket):
            continue

        if bucket == "overdue":
            title = f"Care plan renewal overdue: {client.name}"
            body = (
                f"{client.name}'s {client.get_care_plan_tier_display()} plan "
                f"was due to renew {client.care_plan_renewal:%Y-%m-%d} "
                f"({-days}d ago)."
            )
        else:
            title = f"Care plan renews in {bucket}: {client.name}"
            body = (
                f"{client.name} — {client.get_care_plan_tier_display()} plan "
                f"renews {client.care_plan_renewal:%Y-%m-%d}."
            )

        for user in staff:
            notif = Notification.objects.create(
                user=user,
                type=Notification.Type.CARE_PLAN_RENEWAL,
                title=title,
                body=body,
            )
            try:
                send_push.delay(notif.pk)
            except Exception:
                pass
            notified += 1

        audit_log(
            "care_plan.reminder",
            target=client,
            bucket=bucket,
            days=days,
        )

    return f"care-plan-renewals: {notified} notifications created"


def _bucket_for(days_until: int) -> str | None:
    """Map "days until renewal" to a reminder bucket label."""
    if days_until < 0:
        return "overdue"
    for d in _REMIND_AT_DAYS:
        # ±0 fudge so the daily beat doesn't miss a window if it runs late.
        if days_until == d:
            return f"{d}d"
    return None


@shared_task
def send_nps_survey():
    """Send a once-per-quarter NPS link to each active client's primary contact.

    Quarter key is `YYYY-QN` so the unique constraint on
    `NpsResponse(client, quarter_label)` makes the task idempotent —
    re-running on the same day is a no-op.
    """
    from django.conf import settings
    from django.core.mail import send_mail

    from .models import CarePlanTier, Client, NpsResponse

    today = timezone.localdate()
    quarter = (today.month - 1) // 3 + 1
    label = f"{today.year}-Q{quarter}"

    sent = 0
    qs = Client.objects.exclude(care_plan_tier=CarePlanTier.NONE).prefetch_related(
        "contacts"
    )
    for client in qs:
        if NpsResponse.objects.filter(client=client, quarter_label=label).exists():
            continue
        primary = client.contacts.filter(is_primary=True).first()
        recipient = (primary.email if primary else "") or client.email
        if not recipient:
            continue

        resp = NpsResponse.objects.create(client=client, quarter_label=label)
        link = f"{settings.SITE_URL.rstrip('/')}/nps/{resp.token}/"
        subject = "Quick favour — how are we doing?"
        body = (
            f"Hi {primary.name if primary else client.name},\n\n"
            f"It's been a few months and I'd love to know how we're "
            f"doing. Two seconds — give us a 0-10 here:\n\n{link}\n\n"
            f"Thanks for trusting us with your tech.\n"
            f"Marco — Luma Tech Solutions\n"
        )
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        sent += 1

    return f"nps-survey: {sent} sent for {label}"


def _already_alerted(client, bucket: str) -> bool:
    """Was the same bucket alerted in the trailing 25 hours?

    Uses the audit log as the source of truth (no extra storage).
    """
    from django.contrib.contenttypes.models import ContentType

    cutoff = timezone.now() - timedelta(hours=25)
    return AuditLog.objects.filter(
        action="care_plan.reminder",
        target_ct=ContentType.objects.get_for_model(client.__class__),
        target_id=client.pk,
        created_at__gte=cutoff,
        metadata__bucket=bucket,
    ).exists()
