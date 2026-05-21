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
        LEAD_REMINDER = "lead_reminder", "Lead follow-up reminder"
        REFERRAL_CREDIT = "referral_credit", "Referral credit"
        CARE_PLAN_RENEWAL = "care_plan_renewal", "Care plan renewal reminder"
        INVOICE_OVERDUE = "invoice_overdue", "Invoice overdue"

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


class OutboundWebhook(models.Model):
    """A user's personal alert channel — typically Slack / Teams / Discord.

    When a Notification is created for ``user``, the matching outbound
    webhooks fire a small JSON payload. ``event_filter`` (a JSON list
    of Notification.Type values, empty = all) lets Marco pipe only the
    important categories without burying his own Slack.
    """

    class Format(models.TextChoices):
        SLACK = "slack", "Slack-compatible (Discord too)"
        TEAMS = "teams", "Microsoft Teams (Office 365 connector)"
        GENERIC = "generic", "Generic JSON POST"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="outbound_webhooks",
    )
    name = models.CharField(max_length=80)
    url = models.URLField(max_length=500)
    format = models.CharField(
        max_length=16, choices=Format.choices, default=Format.SLACK
    )
    event_filter = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of Notification.Type values to forward. Leave empty to "
            "forward every notification this user gets."
        ),
    )
    enabled = models.BooleanField(default=True)
    last_called_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.user} → {self.name}"
