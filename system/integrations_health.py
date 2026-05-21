"""Per-integration health snapshot — read by the /system/integrations/
probe and by the staff dashboard tile.

Each check returns ``{"name": str, "configured": bool, "ok": bool,
"detail": str}`` so the consumer can render a uniform list. The
configured-but-not-OK case is the one Marco cares about (e.g. Xero
token expired in the night).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import timezone


def _check_anthropic() -> dict[str, Any]:
    key = getattr(settings, "ANTHROPIC_API_KEY", "") or ""
    return {
        "name": "anthropic",
        "configured": bool(key),
        "ok": bool(key),
        "detail": "key set" if key else "ANTHROPIC_API_KEY unset",
    }


def _check_stripe() -> dict[str, Any]:
    key = getattr(settings, "STRIPE_API_KEY", "") or ""
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or ""
    return {
        "name": "stripe",
        "configured": bool(key),
        "ok": bool(key and secret),
        "detail": "key + webhook secret set"
        if (key and secret)
        else "missing key or webhook secret",
    }


def _check_fcm() -> dict[str, Any]:
    enabled = bool(getattr(settings, "FCM_ENABLED", False))
    return {
        "name": "fcm",
        "configured": enabled,
        "ok": enabled,
        "detail": "FCM enabled" if enabled else "FCM_ENABLED=False (push disabled)",
    }


def _check_imap() -> dict[str, Any]:
    host = getattr(settings, "INBOUND_IMAP_HOST", "") or ""
    return {
        "name": "imap_inbound",
        "configured": bool(host),
        "ok": bool(host),
        "detail": f"poll target: {host}" if host else "INBOUND_IMAP_HOST unset",
    }


def _check_xero() -> dict[str, Any]:
    try:
        from billing.models import XeroConnection
    except Exception:
        return {"name": "xero", "configured": False, "ok": False, "detail": "model missing"}

    conn = XeroConnection.objects.first()
    if conn is None:
        return {
            "name": "xero",
            "configured": False,
            "ok": False,
            "detail": "not connected",
        }
    # Best-effort access to known fields; tolerate older schemas.
    expires_at = getattr(conn, "token_expires_at", None) or getattr(conn, "expires_at", None)
    detail = "connected"
    ok = True
    if expires_at and expires_at < timezone.now():
        ok = False
        detail = "token expired"
    elif expires_at:
        detail = f"token valid until {expires_at:%Y-%m-%d %H:%M}"
    return {"name": "xero", "configured": True, "ok": ok, "detail": detail}


def _check_unifi() -> dict[str, Any]:
    try:
        from clients.models import System
    except Exception:
        return {"name": "unifi", "configured": False, "ok": False, "detail": "model missing"}

    monitored = System.objects.exclude(monitoring_url="").count()
    if not monitored:
        return {
            "name": "unifi",
            "configured": False,
            "ok": False,
            "detail": "no systems have monitoring_url set",
        }
    # Approximate "last poll" by the most recent updated_at on a monitored row.
    latest = (
        System.objects.exclude(monitoring_url="")
        .order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    if latest is None:
        return {
            "name": "unifi",
            "configured": True,
            "ok": False,
            "detail": "no poll yet",
        }
    age_min = (timezone.now() - latest).total_seconds() / 60
    ok = age_min < 120
    return {
        "name": "unifi",
        "configured": True,
        "ok": ok,
        "detail": f"last poll {int(age_min)} min ago",
    }


CHECKERS = [
    _check_anthropic,
    _check_stripe,
    _check_fcm,
    _check_imap,
    _check_xero,
    _check_unifi,
]


def snapshot() -> list[dict[str, Any]]:
    out = []
    for check in CHECKERS:
        try:
            out.append(check())
        except Exception as exc:  # noqa: BLE001
            out.append(
                {
                    "name": check.__name__.removeprefix("_check_"),
                    "configured": False,
                    "ok": False,
                    "detail": f"check raised {type(exc).__name__}",
                }
            )
    return out
