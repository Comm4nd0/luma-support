"""Celery tasks for leads.

`send_followup_reminders` runs on a daily beat (see
`luma_support/settings.py` CELERY_BEAT_SCHEDULE). It scans active leads
whose `next_action_at` has passed and fires an in-app
`Notification(type=LEAD_REMINDER)` + push for the assigned engineer
(or every staff user if unassigned). Dedupes against `last_reminded_at`
so a single overdue lead doesn't re-alert every run.
"""
from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from notifications.models import Notification
from notifications.tasks import send_push

from .models import ACTIVE_STAGES, Lead

# Don't re-remind for the same lead within this window.
_DEDUP_HOURS = 20


@shared_task
def send_followup_reminders():
    now = timezone.now()
    dedup_cutoff = now - timedelta(hours=_DEDUP_HOURS)

    User = get_user_model()
    staff = list(User.objects.filter(role__in=["admin", "engineer"], is_active=True))

    qs = (
        Lead.objects.filter(
            stage__in=ACTIVE_STAGES,
            next_action_at__lt=now,
        )
        .filter(
            # Either never reminded, or last reminder older than the dedup window.
            # Use Q to make NULL count as "never reminded".
        )
        .select_related("assigned_to")
    )

    notified = 0
    for lead in qs:
        if lead.last_reminded_at and lead.last_reminded_at >= dedup_cutoff:
            continue

        if lead.assigned_to_id:
            recipients = [lead.assigned_to]
        else:
            recipients = staff

        title = f"Follow up: {lead.name}"
        body = (
            f"Lead #{lead.pk} — {lead.get_stage_display()}. "
            f"Action was due {lead.next_action_at:%Y-%m-%d %H:%M %Z}."
        )
        for user in recipients:
            notif = Notification.objects.create(
                user=user,
                type=Notification.Type.LEAD_REMINDER,
                title=title,
                body=body,
            )
            send_push.delay(notif.pk)
            notified += 1

        lead.last_reminded_at = now
        lead.save(update_fields=["last_reminded_at", "updated_at"])

    return f"lead-reminders: {notified} notifications created"
