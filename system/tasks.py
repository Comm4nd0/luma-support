"""Celery tasks for the system app — currently just UniFi monitoring."""
from __future__ import annotations

import json
import logging

from celery import shared_task
from django.utils import timezone

from .integrations.unifi import fetch_devices, health_from, serialise

logger = logging.getLogger(__name__)


@shared_task
def refresh_unifi_devices() -> str:
    """Pull device inventory for every type=network System with creds set.

    Refreshes `devices_json`, `health_status`, `last_checked_at` per row.
    On a fresh transition into a non-ok health, a SYSTEM_ALERT
    Notification is fanned out to every active staff user.
    """
    from clients.models import System, SystemType

    qs = (
        System.objects.filter(type=SystemType.NETWORK)
        .exclude(credentials_encrypted="")
        .exclude(monitoring_url="")
        .select_related("client")
    )

    refreshed = 0
    for sys_ in qs:
        try:
            creds = json.loads(sys_.get_credentials() or "{}")
        except json.JSONDecodeError:
            logger.warning("system #%s: credentials are not JSON", sys_.pk)
            continue
        username = creds.get("username") or ""
        password = creds.get("password") or ""
        if not username or not password:
            continue
        site = creds.get("site") or "default"

        old_health = sys_.health_status
        now = timezone.now()
        try:
            result = fetch_devices(
                sys_.monitoring_url, username, password, site
            )
        except Exception:
            logger.exception("system #%s: UniFi fetch failed", sys_.pk)
            sys_.health_status = "down"
            sys_.last_checked_at = now
            sys_.save(
                update_fields=[
                    "health_status",
                    "last_checked_at",
                    "updated_at",
                ]
            )
            _maybe_alert(sys_, old_health)
            continue

        sys_.devices_json = serialise(result)
        sys_.health_status = health_from(result)
        sys_.last_checked_at = now
        sys_.save(
            update_fields=[
                "devices_json",
                "health_status",
                "last_checked_at",
                "updated_at",
            ]
        )
        _maybe_alert(sys_, old_health)
        refreshed += 1

    return f"refresh_unifi_devices: {refreshed} updated"


def _maybe_alert(system_, old_health: str) -> None:
    """Fan out a SYSTEM_ALERT notification when health transitions away from ok."""
    from django.contrib.auth import get_user_model

    from notifications.models import Notification

    if system_.health_status == "ok":
        return
    # Only alert on a fresh transition — skip if the status didn't change.
    if old_health == system_.health_status:
        return

    User = get_user_model()
    title = (
        f"[System Alert] {system_.client.name} — {system_.name}: "
        f"{system_.get_health_status_display()}"
    )
    body = (
        f"Status changed from "
        f"{old_health or 'unknown'} to {system_.health_status}.\n"
        f"Online: {(system_.devices_json or {}).get('online', '?')} · "
        f"Offline: {(system_.devices_json or {}).get('offline', '?')}"
    )
    for u in User.objects.filter(role__in=["admin", "engineer"], is_active=True):
        Notification.objects.create(
            user=u,
            type=Notification.Type.SYSTEM_ALERT,
            title=title,
            body=body,
        )
