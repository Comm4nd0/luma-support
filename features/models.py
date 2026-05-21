"""FeatureFlag — a tiny dial for rolling out work behind a switch.

Use:
    from features import is_enabled
    if is_enabled("ai_triage", user=request.user):
        ...

Flags default to OFF — if the row doesn't exist, ``is_enabled`` returns
False. Add the row from the admin (or via ``manage.py shell``) the first
time you want to turn a feature on.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class FeatureFlag(models.Model):
    name = models.SlugField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True)
    enabled = models.BooleanField(
        default=False,
        help_text="Master switch. When false the flag is off for everyone.",
    )
    percentage = models.PositiveSmallIntegerField(
        default=100,
        help_text=(
            "0-100. When enabled=True, fraction of users that see the "
            "feature. Bucketing is deterministic per user id, so a given "
            "user always either sees or doesn't see the feature for a "
            "given percentage."
        ),
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="+",
        help_text=(
            "If non-empty, the flag is *only* on for these users (ignores "
            "percentage). Use for staff-only or pilot rollouts."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        state = "on" if self.enabled else "off"
        return f"{self.name} ({state}, {self.percentage}%)"
