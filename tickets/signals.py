"""Signals: queue email notifications when ticket state changes."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Ticket, TicketNote


@receiver(post_save, sender=TicketNote)
def _invalidate_ai_summary(sender, instance, created, **kwargs):
    """Drop the cached Claude summary when fresh notes land.

    The summary is a snapshot of the conversation; once a new note is
    posted, the cached version is stale. Cheap to re-derive on demand.
    """
    if not created:
        return
    Ticket.objects.filter(pk=instance.ticket_id).update(
        ai_summary="", ai_summary_at=None
    )


@receiver(pre_save, sender=Ticket)
def _capture_old_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_status = None
        return
    try:
        old = Ticket.objects.get(pk=instance.pk)
        instance._old_status = old.status
    except Ticket.DoesNotExist:
        instance._old_status = None


@receiver(post_save, sender=Ticket)
def _notify_on_change(sender, instance, created, **kwargs):
    # Lazy import to avoid circular import + keep ticket app standalone-importable.
    try:
        from notifications.tasks import send_ticket_update_email
    except Exception:
        return

    def _enqueue(event: str):
        # Don't let a broker outage block ticket writes — log and move on.
        try:
            send_ticket_update_email.delay(instance.pk, event=event)
        except Exception:
            pass

    if created:
        _enqueue("created")
        try:
            from .tasks import triage_new_ticket

            triage_new_ticket.delay(instance.pk)
        except Exception:
            pass
        return

    old = getattr(instance, "_old_status", None)
    if old is not None and old != instance.status:
        _enqueue(f"status:{instance.status}")
        if instance.status == Ticket.Status.CLOSED:
            try:
                from notifications.tasks import send_csat_email

                send_csat_email.delay(instance.pk)
            except Exception:
                pass
