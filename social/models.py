"""Models for Luma's own social-media accounts.

These are *Luma's* accounts (the business's LinkedIn Page, Facebook Page,
Instagram Business profile) — not per-client systems. They live in a
dedicated app rather than reusing `clients.System` because System rows
require a `client` FK and "monitored client infra" semantics.

OAuth tokens are Fernet-encrypted via `clients.encryption`; the same
pattern that protects `System.credentials_encrypted` and
`billing.XeroConnection.refresh_token_encrypted`.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from clients.encryption import decrypt, encrypt


class Platform(models.TextChoices):
    LINKEDIN_PAGE = "linkedin_page", "LinkedIn Page"
    FACEBOOK_PAGE = "facebook_page", "Facebook Page"
    INSTAGRAM_BUSINESS = "instagram_business", "Instagram Business"


class SocialHealth(models.TextChoices):
    UNKNOWN = "", "Unknown"
    OK = "ok", "OK"
    DEGRADED = "degraded", "Degraded"
    DOWN = "down", "Down"


class SocialAccount(models.Model):
    """One row per connected platform. Expect ~3 total."""

    platform = models.CharField(max_length=24, choices=Platform.choices)
    external_id = models.CharField(max_length=128)
    display_name = models.CharField(max_length=200, blank=True)
    avatar_url = models.URLField(blank=True)

    # OAuth — tokens are Fernet-encrypted, never serialised.
    access_token_encrypted = models.TextField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.CharField(max_length=500, blank=True)

    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    connected_at = models.DateTimeField(auto_now_add=True)

    health_status = models.CharField(
        max_length=16, choices=SocialHealth.choices, blank=True
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    # Denormalised stats so the dashboard query is one row, not a fan-out.
    followers = models.IntegerField(null=True, blank=True)
    followers_7d_ago = models.IntegerField(null=True, blank=True)
    last_post_at = models.DateTimeField(null=True, blank=True)
    # Per-platform extras: impressions, reach, engagement_rate, and
    # `followers_history` (list of {"date": ISO, "followers": int}) for
    # the 7-day delta.
    kpis_json = models.JSONField(default=dict, blank=True)

    # Dedup anchor for the >24h-unanswered inbox alert.
    last_overdue_alert_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["platform"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "external_id"],
                name="uniq_social_account_platform_external",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_platform_display()} — {self.display_name or self.external_id}"

    # --- token helpers ----------------------------------------------
    def set_access_token(self, plaintext: str) -> None:
        self.access_token_encrypted = encrypt(plaintext or "")

    def get_access_token(self) -> str:
        return decrypt(self.access_token_encrypted)

    def set_refresh_token(self, plaintext: str) -> None:
        self.refresh_token_encrypted = encrypt(plaintext or "")

    def get_refresh_token(self) -> str:
        return decrypt(self.refresh_token_encrypted)

    @property
    def followers_delta_7d(self) -> int | None:
        if self.followers is None or self.followers_7d_ago is None:
            return None
        return self.followers - self.followers_7d_ago

    @property
    def days_since_last_post(self) -> int | None:
        if self.last_post_at is None:
            return None
        from django.utils import timezone

        return (timezone.now() - self.last_post_at).days


class InboxKind(models.TextChoices):
    DM = "dm", "Direct message"
    MENTION = "mention", "Mention"
    COMMENT = "comment", "Comment"


class InboxStatus(models.TextChoices):
    OPEN = "open", "Open"
    DISMISSED = "dismissed", "Dismissed"
    CONVERTED = "converted", "Converted to ticket"


class SocialInboxItem(models.Model):
    """A DM, mention, or comment that may need Marco's attention."""

    account = models.ForeignKey(
        SocialAccount, on_delete=models.CASCADE, related_name="inbox"
    )
    kind = models.CharField(max_length=12, choices=InboxKind.choices)
    external_id = models.CharField(max_length=255)

    author_handle = models.CharField(max_length=200, blank=True)
    author_display = models.CharField(max_length=200, blank=True)
    preview = models.TextField(blank=True)
    permalink = models.URLField(max_length=1000, blank=True)

    received_at = models.DateTimeField()
    fetched_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=16, choices=InboxStatus.choices, default=InboxStatus.OPEN
    )
    converted_ticket = models.ForeignKey(
        "tickets.Ticket",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="social_inbox_items",
    )

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "external_id"],
                name="uniq_social_inbox_account_external",
            ),
        ]
        indexes = [
            models.Index(
                fields=["account", "status", "-received_at"],
                name="social_inbox_top_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} from {self.author_handle or 'unknown'}"
