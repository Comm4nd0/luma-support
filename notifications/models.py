from django.conf import settings
from django.db import models


class DeviceToken(models.Model):
    """A registered push-notification target for a user's device."""

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    platform = models.CharField(max_length=8, choices=Platform.choices)
    token = models.CharField(max_length=512, unique=True)
    app_version = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self):
        return f"{self.user} ({self.platform})"


class Notification(models.Model):
    class Type(models.TextChoices):
        TICKET_UPDATE = "ticket_update", "Ticket update"
        SLA_WARNING = "sla_warning", "SLA warning"
        SYSTEM_ALERT = "system_alert", "System alert"
        NEW_TICKET = "new_ticket", "New ticket"
        SOCIAL_ALERT = "social_alert", "Social account alert"

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
