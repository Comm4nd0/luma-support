"""Signals: queue email notifications when ticket state changes."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Ticket


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
        return

    old = getattr(instance, "_old_status", None)
    if old is not None and old != instance.status:
        _enqueue(f"status:{instance.status}")
