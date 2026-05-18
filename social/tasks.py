"""Celery tasks: periodic refresh + daily KPI snapshot."""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from notifications.models import Notification

from .integrations import SocialFetchResult, redact_error
from .integrations import facebook as fb_integration
from .integrations import instagram as ig_integration
from .integrations import linkedin as li_integration
from .models import InboxStatus, Platform, SocialAccount, SocialInboxItem

logger = logging.getLogger(__name__)

# Map platform to its integration module — `fetch_for` / `health_from` are
# resolved on the module at call time so tests can monkeypatch them.
_INTEGRATIONS = {
    Platform.LINKEDIN_PAGE: li_integration,
    Platform.FACEBOOK_PAGE: fb_integration,
    Platform.INSTAGRAM_BUSINESS: ig_integration,
}

# Suppress duplicate overdue alerts within this window.
_OVERDUE_ALERT_DEDUP = timedelta(hours=12)
# An inbox item that's been OPEN longer than this fires SOCIAL_ALERT.
_OVERDUE_AGE = timedelta(hours=24)


@shared_task
def refresh_social_accounts() -> str:
    """Pull stats + inbox for every connected SocialAccount.

    Mirrors `system.tasks.refresh_unifi_devices` — iterate, fetch,
    persist, alert on health transition. Each row's exception is
    isolated so one broken integration doesn't block the others.
    """
    refreshed = 0
    for account in SocialAccount.objects.exclude(access_token_encrypted=""):
        integration = _INTEGRATIONS.get(account.platform)
        if integration is None:
            continue
        old_health = account.health_status
        now = timezone.now()
        try:
            result = integration.fetch_for(account)
        except Exception as exc:  # noqa: BLE001 — isolate per row
            logger.exception(
                "social account #%s (%s): fetch failed", account.pk, account.platform
            )
            account.health_status = "down"
            account.last_checked_at = now
            account.last_error = redact_error(exc)
            account.save(
                update_fields=[
                    "health_status",
                    "last_checked_at",
                    "last_error",
                    "updated_at",
                ]
            )
            _maybe_alert(account, old_health)
            continue

        _apply_result(account, result, integration.health_from)
        account.last_checked_at = now
        account.save(
            update_fields=[
                "health_status",
                "last_checked_at",
                "last_error",
                "followers",
                "last_post_at",
                "kpis_json",
                "updated_at",
            ]
        )
        _persist_inbox(account, result)
        _maybe_alert(account, old_health)
        _maybe_overdue_alert(account, now)
        refreshed += 1
    return f"refresh_social_accounts: {refreshed} updated"


def _apply_result(account: SocialAccount, result: SocialFetchResult, health_from):
    if result.followers is not None:
        account.followers = result.followers
    if result.last_post_at is not None:
        account.last_post_at = result.last_post_at
    if result.kpis:
        merged = dict(account.kpis_json or {})
        merged.update(result.kpis)
        account.kpis_json = merged
    account.health_status = health_from(result)
    account.last_error = result.partial_reason or ""


def _persist_inbox(account: SocialAccount, result: SocialFetchResult) -> None:
    """Idempotent insert: `(account, external_id)` is unique.

    `update_or_create` overwrites preview/permalink (in case the
    provider re-emits an edited item) but preserves `status` so a
    dismissed item is not resurrected by a later refresh — `defaults`
    deliberately omits `status`.
    """
    for fetched in result.inbox_items:
        if not fetched.external_id or fetched.received_at is None:
            continue
        SocialInboxItem.objects.update_or_create(
            account=account,
            external_id=fetched.external_id,
            defaults={
                "kind": fetched.kind,
                "author_handle": fetched.author_handle,
                "author_display": fetched.author_display,
                "preview": fetched.preview,
                "permalink": fetched.permalink,
                "received_at": fetched.received_at,
            },
        )


def _maybe_alert(account: SocialAccount, old_health: str) -> None:
    """Fan out a SOCIAL_ALERT when health transitions away from ok."""
    if account.health_status == "ok":
        return
    if old_health == account.health_status:
        return
    User = get_user_model()
    title = (
        f"[Social] {account.get_platform_display()} "
        f"{account.display_name or account.external_id}: "
        f"{account.get_health_status_display() or 'unknown'}"
    )
    body = (
        f"Status changed from {old_health or 'unknown'} to {account.health_status}."
    )
    if account.last_error:
        body += f"\n{account.last_error}"
    for u in User.objects.filter(role__in=["admin", "engineer"], is_active=True):
        Notification.objects.create(
            user=u,
            type=Notification.Type.SOCIAL_ALERT,
            title=title,
            body=body,
        )


def _maybe_overdue_alert(account: SocialAccount, now) -> None:
    """Alert once when an OPEN inbox item crosses the 24h threshold.

    Deduped via `SocialAccount.last_overdue_alert_at` — so the next
    refresh inside the dedup window stays silent even if more items
    cross the threshold.
    """
    if (
        account.last_overdue_alert_at
        and (now - account.last_overdue_alert_at) < _OVERDUE_ALERT_DEDUP
    ):
        return
    cutoff = now - _OVERDUE_AGE
    overdue = SocialInboxItem.objects.filter(
        account=account, status=InboxStatus.OPEN, received_at__lte=cutoff
    ).order_by("received_at")
    overdue_count = overdue.count()
    if overdue_count == 0:
        return
    User = get_user_model()
    title = (
        f"[Social] {overdue_count} unanswered on "
        f"{account.get_platform_display()}"
    )
    oldest = overdue.first()
    age_h = int((now - oldest.received_at).total_seconds() // 3600)
    body = (
        f"Oldest open item is {age_h}h old "
        f"(from {oldest.author_handle or 'unknown'}): "
        f"{(oldest.preview or '')[:120]}"
    )
    for u in User.objects.filter(role__in=["admin", "engineer"], is_active=True):
        Notification.objects.create(
            user=u,
            type=Notification.Type.SOCIAL_ALERT,
            title=title,
            body=body,
        )
    account.last_overdue_alert_at = now
    account.save(update_fields=["last_overdue_alert_at", "updated_at"])


@shared_task
def refresh_social_kpis_daily() -> str:
    """Snapshot follower count for the 7-day delta on the dashboard."""
    today = timezone.localdate().isoformat()
    updated = 0
    for account in SocialAccount.objects.exclude(followers__isnull=True):
        history = list((account.kpis_json or {}).get("followers_history") or [])
        # One snapshot per day; replace if today already exists.
        history = [h for h in history if h.get("date") != today]
        history.append({"date": today, "followers": account.followers})
        # Keep last 30 days only.
        history = history[-30:]
        new_kpis = dict(account.kpis_json or {})
        new_kpis["followers_history"] = history

        cutoff = (timezone.now() - timedelta(days=7)).date().isoformat()
        candidates = [h for h in history if h.get("date") <= cutoff]
        if candidates:
            account.followers_7d_ago = candidates[-1]["followers"]
        account.kpis_json = new_kpis
        account.save(
            update_fields=["kpis_json", "followers_7d_ago", "updated_at"]
        )
        updated += 1
    return f"refresh_social_kpis_daily: {updated} snapshots"
