"""AuditLog — durable record of sensitive actions.

Rows are written via `audit.log()`. They're never edited; on retention
policies an admin can prune older rows via the admin UI.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=64)
    # Generic FK so any model can be a target. Nullable for actions
    # that don't have a single object (e.g. login_failed).
    target_ct = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    target_repr = models.CharField(max_length=255, blank=True)
    target = GenericForeignKey("target_ct", "target_id")

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        who = self.actor.email if self.actor_id else "system"
        what = self.target_repr or "—"
        return f"{self.created_at:%Y-%m-%d %H:%M} {who} {self.action} {what}"
