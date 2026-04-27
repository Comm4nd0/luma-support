from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        TICKET_UPDATE = "ticket_update", "Ticket update"
        SLA_WARNING = "sla_warning", "SLA warning"
        SYSTEM_ALERT = "system_alert", "System alert"
        NEW_TICKET = "new_ticket", "New ticket"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    related_ticket = models.ForeignKey(
        "tickets.Ticket",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    read = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read"])]

    def __str__(self):
        return f"{self.type}: {self.title}"
