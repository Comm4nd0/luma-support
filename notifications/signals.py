"""Signals: enqueue a push when a Notification is created.

Triggering off Notification (not Ticket) means SLA-warning notifications
created by ``check_sla_warnings`` are pushed for free, without each call
site needing to remember to fire a push.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .tasks import send_push


@receiver(post_save, sender=Notification)
def push_notification_on_create(sender, instance, created, **kwargs):
    if not created:
        return
    send_push.delay(instance.pk)
